"""Exhaustive bounded two-permit, three-version authority model.
State deduplication is not DPOR. This is a model, not adapter conformance.
"""
import json
from collections import deque

# (version, actor PCs, issued versions, effects, receipt mask)
# actors: permit A issue/commit; permit B issue/commit; authority revoke twice
INITIAL=(0,(0,0,0),(-1,-1),(0,0),0)

def successors(s,stale=False):
    version,pc,issued,effects,receipts=s
    for actor in range(2):
        if pc[actor]==0:
            n=list(pc);n[actor]=1
            i=list(issued);i[actor]=version
            yield ('issue_'+str(actor),(version,tuple(n),tuple(i),effects,receipts),False)
        if pc[actor]==1:
            n=list(pc);n[actor]=2
            # Version 0 and 1 are valid; version 2 revokes all permits.
            allowed=issued[actor]>=0 and (stale or (version<2 and issued[actor]==version))
            e=list(effects);e[actor]+=int(allowed)
            label=('commit_' if allowed else 'deny_')+str(actor)
            unsafe=allowed and (version>=2 or issued[actor]!=version)
            yield (label,(version,tuple(n),issued,tuple(e),receipts),unsafe)
        if pc[actor]==2 and not (receipts & (1<<actor)):
            yield ('receipt_'+str(actor),(version,pc,issued,effects,receipts|(1<<actor)),False)
    if pc[2]<2:
        n=list(pc);n[2]+=1
        yield ('authority_version_'+str(version+1),(version+1,tuple(n),issued,effects,receipts),False)

def explore(stale=False,limit=100000):
    q=deque([(INITIAL,())]);seen={INITIAL};edges=0;terminal=0;violations=[]
    while q:
        s,trace=q.popleft();nxt=list(successors(s,stale))
        if not nxt:terminal+=1
        for action,new,unsafe in nxt:
            edges+=1
            if unsafe:violations.append({'invariant':'fresh-authority','trace':trace+(action,)})
            if any(x>1 for x in new[3]):violations.append({'invariant':'at-most-once','trace':trace+(action,)})
            if new not in seen:
                seen.add(new)
                if len(seen)>limit:return {'status':'INCOMPLETE','states':len(seen),'edges':edges,'violations':violations}
                q.append((new,trace+(action,)))
    # Counts below distinguish transition-level counterexamples from root causes.
    # A single stale-authority defect may occur in many reachable schedules.
    root_causes=sorted({v['invariant'] for v in violations})
    return {'status':'FAIL' if violations else 'PASS','states':len(seen),'edges':edges,'terminal':terminal,
            'violations':violations,'violation_occurrences':len(violations),
            'unique_invariant_classes':root_causes,'unique_invariant_class_count':len(root_causes),
            'bound':{'permits':2,'versions':3,'actors':3},'method':'bounded exhaustive BFS; no DPOR'}

if __name__=='__main__':
    result={'normal':explore(),'stale_mutant':explore(stale=True)}
    print(json.dumps(result,indent=2))
    if result['normal']['status']!='PASS' or result['stale_mutant']['status']!='FAIL':raise SystemExit(1)
