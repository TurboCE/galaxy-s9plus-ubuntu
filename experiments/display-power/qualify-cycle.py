#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Bounded actual long-idle panel qualification; explicitly changes screen state."""
import argparse,importlib.util,json,os,select,subprocess,tempfile,threading,time
from pathlib import Path

def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--confirm-sm-g965n-backed-up-panel-cycle',required=True,action='store_true')
 p.add_argument('--dwell-seconds',type=int,default=90);p.add_argument('--cycles',type=int,default=2)
 p.add_argument('--leave-off',action='store_true');a=p.parse_args()
 if not 60<=a.dwell_seconds<=300 or not 1<=a.cycles<=3:p.error('Bounded long-idle trial required')
 if os.geteuid()!=0:raise RuntimeError('Root required')
 guard=load('guard',Path('/usr/local/lib/g965n-led-trial/led-control.py'));guard.preflight()
 m=load('panel',Path('/usr/local/lib/g965n-display-power/power-key.py'))
 prefix=m.session_prefix('ubuntu',1000);initial=m.panel_mode()
 os.umask(0o077);base=Path('/var/lib/g965n-display-power');base.mkdir(mode=0o700,exist_ok=True)
 root=Path(tempfile.mkdtemp(prefix='long-cycle-',dir=base));(base/'latest-cycle').write_text(str(root))
 result={'status':'running','dwell_seconds':a.dwell_seconds,'cycles':[]}
 def save():(root/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 fd=os.open(m.discover(),os.O_RDONLY|os.O_NONBLOCK|os.O_CLOEXEC)
 wake=m.WakeInput();external=False
 def physical_input():
  nonlocal external
  if not select.select([fd],[],[],0)[0]:return False
  data=os.read(fd,m.EVENT.size*64)
  for off in range(0,len(data),m.EVENT.size):
   _,_,kind,code,value=m.EVENT.unpack(data[off:off+m.EVENT.size])
   if kind==1 and code==116 and value==1:external=True
  return external
 def battery_safe():
  # No load/clock/charge changes: stop screen cycling if measurement is unsafe.
  lines=Path('/var/lib/g965n-charge-observer/samples.jsonl').read_text().splitlines()
  for l in reversed(lines):
   try:r=json.loads(l)
   except ValueError:continue
   if 'end_monotonic_ns' not in r:continue
   age=time.clock_gettime_ns(time.CLOCK_BOOTTIME)-r['end_monotonic_ns']
   return (0<=age<35_000_000_000 and r['temperature']['battery']['temperature_deci_c']<420 and
           int(Path('/sys/class/power_supply/max170xx_battery/voltage_now').read_text())>=3500000)
  return False
 try:
  for number in range(a.cycles):
   if not battery_safe():raise RuntimeError('Unsafe/stale power measurement')
   if m.panel_mode()!=3:m.toggle(prefix,0,wake)
   cycle={'number':number+1,'status':'idle','off_start':time.monotonic()};result['cycles'].append(cycle);save()
   end=time.monotonic()+a.dwell_seconds
   while time.monotonic()<end:
    if physical_input():raise RuntimeError('Physical key interrupted automatic trial')
    if m.panel_mode()!=3:raise RuntimeError('Panel did not stay OFF during idle')
    time.sleep(.25)
   if not battery_safe():raise RuntimeError('Unsafe/stale power measurement')
   trace=[];done=threading.Event()
   backlights=list(Path('/sys/class/backlight').glob('*/actual_brightness'))
   def record():
    start=time.monotonic()
    while not done.is_set():
     trace.append({'elapsed':round(time.monotonic()-start,3),'mode':m.panel_mode(),
        'brightness':int(backlights[0].read_text()) if len(backlights)==1 else None})
     time.sleep(.02)
   thread=threading.Thread(target=record,daemon=True);thread.start()
   try:
    m.toggle(prefix,3,wake)
    time.sleep(5)
   finally:done.set();thread.join(timeout=2)
   cycle['trace']=trace
   first=next((i for i,x in enumerate(trace) if x['mode']==0 and (x['brightness'] is None or x['brightness']>0)),None)
   if first is None:raise RuntimeError('Panel never lit')
   if any(x['mode']!=0 or x['brightness']==0 for x in trace[first:]):raise RuntimeError('Panel blanked again after first light')
   if physical_input():raise RuntimeError('Physical key interrupted automatic trial')
   cycle.update(status='passed',first_light_seconds=trace[first]['elapsed']);save()
  result['status']='passed'
 except Exception as error:
  result.update(status='inconclusive' if external else 'failed',reason=str(error))
 finally:
  if not external:
   if a.leave_off and m.panel_mode()!=3:m.toggle(prefix,0,wake)
   elif not a.leave_off and initial==0 and m.panel_mode()!=0:m.toggle(prefix,3,wake)
  wake.close();os.close(fd);save()
 print(json.dumps({'status':result['status'],'reason':result.get('reason'),'cycles':[{'number':x['number'],'status':x['status']} for x in result['cycles']]}),flush=True)
 if result['status']=='failed':raise SystemExit(1)

if __name__=='__main__':main()
