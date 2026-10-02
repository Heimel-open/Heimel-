---- MODULE AuthorityConfinement ----
EXTENDS Naturals, Sequences, FiniteSets

CONSTANTS Principals, Rights, PolicyEnvelope, RootPrincipal, MaxCommits

ASSUME /\ Principals # {}
       /\ Rights # {}
       /\ PolicyEnvelope \subseteq Rights
       /\ RootPrincipal \in Principals
       /\ MaxCommits \in Nat
       /\ MaxCommits > 0

VARIABLES authority,
          permitScope,
          committed

vars == <<authority, permitScope, committed>>

Init ==
    /\ authority = [p \in Principals |->
          IF p = RootPrincipal THEN PolicyEnvelope ELSE {}]
    /\ permitScope = [p \in Principals |-> {}]
    /\ committed = <<>>

Delegate(src, dst, granted) ==
    /\ src \in Principals
    /\ dst \in Principals
    /\ granted \subseteq authority[src]
    /\ authority' = [authority EXCEPT ![dst] = @ \cup granted]
    /\ UNCHANGED <<permitScope, committed>>

Revoke(p, removed) ==
    /\ p \in Principals
    /\ removed \subseteq Rights
    /\ authority' = [authority EXCEPT ![p] = @ \ removed]
    /\ permitScope' = [permitScope EXCEPT ![p] = @ \ removed]
    /\ UNCHANGED committed

IssuePermit(p, scope) ==
    /\ p \in Principals
    /\ scope \subseteq authority[p]
    /\ permitScope' = [permitScope EXCEPT ![p] = scope]
    /\ UNCHANGED <<authority, committed>>

Commit(p, required) ==
    /\ p \in Principals
    /\ Len(committed) < MaxCommits
    /\ required \subseteq permitScope[p]
    /\ required \subseteq authority[p]
    /\ committed' = Append(committed,
          [principal |-> p,
           required |-> required,
           permitAtCommit |-> permitScope[p],
           authorityAtCommit |-> authority[p]])
    /\ permitScope' = [permitScope EXCEPT ![p] = {}]
    /\ UNCHANGED authority

Next ==
    \/ \E src, dst \in Principals, granted \in SUBSET Rights : Delegate(src, dst, granted)
    \/ \E p \in Principals, removed \in SUBSET Rights : Revoke(p, removed)
    \/ \E p \in Principals, scope \in SUBSET Rights : IssuePermit(p, scope)
    \/ \E p \in Principals, required \in SUBSET Rights : Commit(p, required)

Spec == Init /\ [][Next]_vars

TypeOK ==
    /\ authority \in [Principals -> SUBSET Rights]
    /\ permitScope \in [Principals -> SUBSET Rights]
    /\ Len(committed) <= MaxCommits

AuthorityConfinement ==
    \A p \in Principals : authority[p] \subseteq PolicyEnvelope

PermitConfinement ==
    \A p \in Principals : permitScope[p] \subseteq authority[p]

Integrity ==
    \A i \in 1..Len(committed) :
        /\ committed[i].required \subseteq committed[i].permitAtCommit
        /\ committed[i].permitAtCommit \subseteq committed[i].authorityAtCommit
        /\ committed[i].authorityAtCommit \subseteq PolicyEnvelope

====
