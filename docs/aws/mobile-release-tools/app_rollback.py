"""Restore the preceding source only; preserve all current customer data."""
from app_common import *
from app_cutover import healthy,dropin,install_interrupt_handler

def main():
    preflight=json.loads((RECEIPT/'app-preflight.json').read_text())
    assert preflight['old']==str(OLD) and preflight['new']==str(RELEASE)
    has_override=privileged_exists(CONF)
    if has_override:assert run('sudo','cat',CONF).stdout==dropin(),'Unknown release override; refuse to remove'
    errors=[]
    def attempt(*args):
        try:run(*args)
        except Exception as failure:errors.append({'step':[str(x) for x in args[:4]],'error':type(failure).__name__})
    attempt('sudo','systemctl','stop','demo-studio')
    if has_override:attempt('sudo','mv',CONF,RECEIPT/('app-removed-override-'+str(time.time_ns())+'.conf'))
    attempt('sudo','systemctl','daemon-reload');attempt('sudo','systemctl','start','demo-studio')
    try:
        assert state('WorkingDirectory')==str(OLD) and selected_health(healthy())==preflight['health']
    except Exception as failure:errors.append({'step':'verify previous application','error':type(failure).__name__})
    save('app-manual-rollback-'+str(time.time_ns())+'.json',{'errors':errors,'customer_data_retained':True,'proxy_unchanged':True})
    print(json.dumps({'rollback_errors':len(errors),'customer_data_retained':True}))
    assert not errors,'Inspect private rollback receipt; no data restore was attempted'

if __name__=='__main__':install_interrupt_handler();main()
