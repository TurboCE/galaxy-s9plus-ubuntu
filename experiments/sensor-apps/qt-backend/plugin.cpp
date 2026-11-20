// SPDX-License-Identifier: GPL-2.0-only

#include <QtCore/QDir>
#include <QtCore/QFile>
#include <QtCore/QTimer>
#include <QtCore/QtMath>
#include <QtNetwork/QLocalSocket>
#include <QtSensors/QAccelerometer>
#include <QtSensors/QCompass>
#include <QtSensors/QGyroscope>
#include <QtSensors/QPressureSensor>
#include <QtSensors/QProximitySensor>
#include <QtSensors/QSensorBackend>
#include <QtSensors/QSensorManager>
#include <QtSensors/QSensorPluginInterface>
#include <QtSensors/QTiltSensor>

#include <array>
#include <cmath>
#include <ctime>

namespace {

QByteArray readAttribute(const QString &fileName)
{
    QFile file(fileName);
    return file.open(QIODevice::ReadOnly) ? file.read(256).trimmed() : QByteArray();
}

bool number(const QByteArray &text, double &value)
{
    bool ok;
    value = text.toDouble(&ok);
    return ok && std::isfinite(value);
}

quint64 timestamp()
{
    timespec time{};
    clock_gettime(CLOCK_MONOTONIC, &time);
    return quint64(time.tv_sec) * 1000000 + time.tv_nsec / 1000;
}

class IioDevice
{
public:
    explicit IioDevice(QByteArray name) : name(name) {}

    bool locate()
    {
        if (!path.isEmpty() && readAttribute(path + "/name") == name)
            return true;

        path.clear();
        const QDir devices("/sys/bus/iio/devices");
        for (const auto &entry : devices.entryList({"iio:device*"}, QDir::Dirs)) {
            const auto candidate = devices.filePath(entry);
            if (readAttribute(candidate + "/name") == name) {
                path = candidate;
                return true;
            }
        }
        return false;
    }

    bool read(const QString &attribute, double &value) const
    {
        return number(readAttribute(path + '/' + attribute), value);
    }

    bool readAxes(const QString &stem, std::array<double, 3> &axes) const
    {
        return read(stem + "_x_raw", axes[0]) && read(stem + "_y_raw", axes[1])
            && read(stem + "_z_raw", axes[2]);
    }

    bool mountAcceleration(std::array<double, 3> &axes) const
    {
        auto matrix = readAttribute(path + "/in_accel_mount_matrix");
        matrix.replace(';', ',');
        const auto fields = matrix.split(',');
        if (fields.size() != 9)
            return false;

        std::array<double, 3> mounted{};
        for (int row = 0; row < 3; ++row) {
            for (int col = 0; col < 3; ++col) {
                double coefficient;
                if (!number(fields.at(3 * row + col).trimmed(), coefficient))
                    return false;
                mounted[row] += coefficient * axes[col];
            }
        }
        axes = mounted;
        return true;
    }

private:
    const QByteArray name;
    QString path;
};

template<class Reading>
class PollBackend : public QSensorBackend
{
public:
    PollBackend(QSensor *sensor, const QByteArray &deviceName)
        : QSensorBackend(sensor), device(deviceName)
    {
        setReading<Reading>(&reading);
        // This rate is for sysfs polling. SSP controls the hardware cadence.
        addDataRate(5, 5);
        connect(&timer, &QTimer::timeout, this, [this] {
            if (device.locate() && sample()) {
                reading.setTimestamp(timestamp());
                newReadingAvailable();
            }
        });
    }

    void start() override
    {
        if (!device.locate()) {
            sensorStopped();
            return;
        }
        timer.start(200);
    }

    void stop() override { timer.stop(); }

protected:
    virtual bool sample() = 0;
    IioDevice device;
    Reading reading;

private:
    QTimer timer;
};

class AccelerationBackend : public PollBackend<QAccelerometerReading>
{
public:
    explicit AccelerationBackend(QSensor *sensor)
        : PollBackend(sensor, "g965n-ssp-accel") {}

private:
    bool sample() override
    {
        std::array<double, 3> axes;
        double scale;
        if (!device.readAxes("in_accel", axes) || !device.mountAcceleration(axes)
            || !device.read("in_accel_scale", scale) || scale <= 0)
            return false;
        reading.setX(axes[0] * scale);
        reading.setY(axes[1] * scale);
        reading.setZ(axes[2] * scale);
        return true;
    }
};

class TiltBackend : public PollBackend<QTiltReading>
{
    Q_OBJECT

public:
    explicit TiltBackend(QSensor *sensor) : PollBackend(sensor, "g965n-ssp-accel") {}

public slots:
    void calibrate()
    {
        offsetRoll = roll;
        offsetPitch = pitch;
    }

private:
    bool sample() override
    {
        std::array<double, 3> axes;
        if (!device.readAxes("in_accel", axes) || !device.mountAcceleration(axes))
            return false;
        const auto [x, y, z] = axes;
        if (x == 0 && y == 0 && z == 0)
            return false;

        roll = std::atan2(y, z);
        pitch = std::atan2(-x, std::hypot(y, z));
        reading.setXRotation(wrappedDegrees(roll - offsetRoll));
        reading.setYRotation(wrappedDegrees(pitch - offsetPitch));
        return true;
    }

    static double wrappedDegrees(double radians)
    {
        return std::remainder(qRadiansToDegrees(radians), 360.0);
    }

    double roll = 0;
    double pitch = 0;
    double offsetRoll = 0;
    double offsetPitch = 0;
};

class ProximityBackend : public PollBackend<QProximityReading>
{
public:
    explicit ProximityBackend(QSensor *sensor)
        : PollBackend(sensor, "g965n-ssp-proximity") {}

private:
    bool sample() override
    {
        double value, threshold;
        if (!device.read("in_proximity_raw", value)
            || !device.read("in_proximity_nearlevel", threshold))
            return false;
        reading.setClose(value >= threshold);
        return true;
    }
};

class GyroscopeBackend : public PollBackend<QGyroscopeReading>
{
public:
    explicit GyroscopeBackend(QSensor *sensor)
        : PollBackend(sensor, "g965n-ssp-gyro") {}

private:
    bool sample() override
    {
        std::array<double, 3> axes;
        if (!device.readAxes("in_anglvel", axes))
            return false;
        // Stock G965N HAL passes these same SSP axes through. Its
        // 0.035 deg/s factor is divided by 1000 for the signed32 IIO payload.
        constexpr double degreesPerSecondPerCount = 0.035 / 1000;
        reading.setX(axes[0] * degreesPerSecondPerCount);
        reading.setY(axes[1] * degreesPerSecondPerCount);
        reading.setZ(axes[2] * degreesPerSecondPerCount);
        return true;
    }
};

class PressureBackend : public PollBackend<QPressureReading>
{
public:
    explicit PressureBackend(QSensor *sensor)
        : PollBackend(sensor, "g965n-ssp-pressure") {}

    bool isFeatureSupported(QSensor::Feature feature) const override
    {
        return feature == QSensor::PressureSensorTemperature;
    }

private:
    bool sample() override
    {
        double raw, scale, temperature;
        if (!device.read("in_pressure_raw", raw) || raw <= 0
            || !device.read("in_pressure_scale", scale) || scale <= 0
            || !device.read("in_temp_input", temperature))
            return false;
        reading.setPressure(raw * scale * 1000); // kPa to Pa
        reading.setTemperature(temperature / 1000); // millidegrees C to degrees C
        return true;
    }
};

class CompassBackend : public QSensorBackend
{
public:
    explicit CompassBackend(QSensor *sensor) : QSensorBackend(sensor)
    {
        setReading<QCompassReading>(&reading);
        addDataRate(1, 1);
        socket.setReadBufferSize(256);
        connect(&socket, &QLocalSocket::readyRead, this, [this] { readHeadings(); });
        connect(&retry, &QTimer::timeout, this, [this] { connectToRelay(); });
    }

    void start() override
    {
        retry.start(1000);
        connectToRelay();
    }

    void stop() override
    {
        retry.stop();
        socket.abort();
    }

private:
    void connectToRelay()
    {
        if (socket.state() == QLocalSocket::UnconnectedState)
            socket.connectToServer("/run/g965n-compass/heading.sock", QIODevice::ReadOnly);
    }

    void readHeadings()
    {
        while (socket.canReadLine()) {
            double heading;
            if (!number(socket.readLine().trimmed(), heading) || heading < 0 || heading >= 360)
                continue;
            reading.setAzimuth(heading);
            // The relay exports heading only. It has no Qt calibration confidence.
            reading.setCalibrationLevel(0);
            reading.setTimestamp(timestamp());
            newReadingAvailable();
        }
        if (socket.bytesAvailable() >= 256)
            socket.abort();
    }

    QCompassReading reading;
    QLocalSocket socket;
    QTimer retry;
};

class SensorPlugin : public QObject, public QSensorPluginInterface, public QSensorBackendFactory
{
    Q_OBJECT
    Q_PLUGIN_METADATA(IID "com.qt-project.Qt.QSensorPluginInterface/1.0")
    Q_INTERFACES(QSensorPluginInterface)

public:
    void registerSensors() override
    {
        QSensorManager::registerBackend(QAccelerometer::type, "g965n.accelerometer", this);
        QSensorManager::registerBackend(QTiltSensor::type, "g965n.tilt", this);
        QSensorManager::registerBackend(QProximitySensor::type, "g965n.proximity", this);
        QSensorManager::registerBackend(QGyroscope::type, "g965n.gyroscope", this);
        QSensorManager::registerBackend(QPressureSensor::type, "g965n.pressure", this);
        QSensorManager::registerBackend(QCompass::type, "g965n.compass", this);
    }

    QSensorBackend *createBackend(QSensor *sensor) override
    {
        const auto id = sensor->identifier();
        if (id == "g965n.accelerometer")
            return new AccelerationBackend(sensor);
        if (id == "g965n.tilt")
            return new TiltBackend(sensor);
        if (id == "g965n.proximity")
            return new ProximityBackend(sensor);
        if (id == "g965n.gyroscope")
            return new GyroscopeBackend(sensor);
        if (id == "g965n.pressure")
            return new PressureBackend(sensor);
        if (id == "g965n.compass")
            return new CompassBackend(sensor);
        return nullptr;
    }
};

} // namespace

#include "plugin.moc"
