"""Bounded exhaustive state-space explorer for a public authority/effect model.

Enumerates enabled actor steps and memoizes equivalent model states.
This is NOT DPOR and does not prove the external adapter's implementation.
"""
import argparse
import hashlib
import json
from collections import deque

# State: authority version, revoked, permit-issued, actor program counters,
# number of committed effects, crash/restart state, durable receipt.
def initial():
    return ('A1', False, False, (0,0,0), 0, False, False)

def transitions(state, mutant=False):
    version,revoked,permit,pcs,effects,crashed,receipt=state
    options=[]
    def add(label,**change):
        d=dict(version=version,revoked=revoked,permit=permit,pcs=pcs,effects=effects,crashed=crashed,receipt=receipt)
        d.update(change)
        options.append((label,(d['version'],d['revoked'],d['permit'],d['pcs'],d['effects'],d['crashed'],d['receipt'])))
    # actor 0: issue permit, then attempt effect; actor 1: revoke authority;
    # actor 2: crash then recover. All actions are individually schedulable.
    if pcs[0]==0 and not crashed:
        p=list(pcs);p[0]=1;add('issue_permit',pcs=tuple(p),permit=not revoked)
    if pcs[0]==1 and not crashed:
        p=list(pcs);p[0]=2
        permitted=permit and (not revoked or mutant)
        add('commit' if permitted else 'deny',pcs=tuple(p),effects=effects+int(permitted))
    if pcs[1]==0:
        p=list(pcs);p[1]=1;add('revoke',pcs=tuple(p),revoked=True,version='A2')
    if pcs[2]==0:
        p=list(pcs);p[2]=1;add('crash',pcs=tuple(p),crashed=True)
    if pcs[2]==1:
        p=list(pcs);p[2]=2;add('restart',pcs=tuple(p),crashed=False)
    if pcs[0]==2 and not receipt and not crashed:
        add('persist_receipt',receipt=True)
    return options

def violation(state,trace):
    version,revoked,permit,pcs,effects,crashed,receipt=state
    if effects>1:return 'at-most-once'
    if trace and trace[-1]=='commit' and revoked:return 'commit-after-revocation'
    return None

def explore(mutant=False,max_states=100000):
    queue=deque([(initial(),())]);seen={initial()};edges=0;terminal=0;violations=[]
    while queue:
        state,trace=queue.popleft()
        issue=violation(state,trace)
        if issue:violations.append({'invariant':issue,'trace':trace});continue
        nxt=transitions(state,mutant)
        if not nxt:terminal+=1
        for label,new in nxt:
            edges+=1
            # Check transition-local safety BEFORE state deduplication: the same
            # terminal state can be reached by safe and unsafe histories.
            if label=='commit' and state[1]:
                violations.append({'invariant':'commit-after-revocation','trace':trace+(label,)})
                continue
            if new not in seen:
                seen.add(new)
                if len(seen)>max_states:
                    return {'status':'INCOMPLETE','states':len(seen),'edges':edges,'reason':'state limit','violations':violations}
                queue.append((new,trace+(label,)))
    return {'status':'FAIL' if violations else 'PASS','states':len(seen),'edges':edges,'terminal':terminal,'violations':violations,
            'bound':{'actors':3,'permits':1,'authority_versions':2,'crashes':1},'method':'exhaustive reachable-state BFS with state memoization (not DPOR)'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--max-states',type=int,default=100000);p.add_argument('--output');a=p.parse_args()
    result={'normal':explore(max_states=a.max_states),'mutant_stale':explore(mutant=True,max_states=a.max_states)}
    result['model_sha256']=hashlib.sha256(open(__file__,'rb').read()).hexdigest()
    print(json.dumps(result,indent=2))
    if a.output:open(a.output,'w').write(json.dumps(result,indent=2)+'\n')
    if result['normal']['status']!='PASS' or result['mutant_stale']['status']!='FAIL':raise SystemExit(1)
if __name__=='__main__':main()
