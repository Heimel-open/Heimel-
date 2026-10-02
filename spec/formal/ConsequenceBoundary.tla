---- MODULE ConsequenceBoundary ----
EXTENDS Naturals, Sequences, FiniteSets

CONSTANTS Permits, Digests, NoDigest, MaxTime, PermitTTL, MaxRevision

ASSUME /\ Permits # {}
       /\ Digests # {}
       /\ NoDigest \notin Digests
       /\ MaxTime \in Nat
       /\ PermitTTL \in Nat
       /\ PermitTTL > 0
       /\ MaxRevision \in Nat
       /\ MaxRevision > 1

VARIABLES authorityRevision,
          authorizedDigest,
          issued,
          consumed,
          permitDigest,
          permitRevision,
          permitExpiry,
          now,
          missingRequired,
          decision,
          committed

vars == <<authorityRevision, authorizedDigest, issued, consumed,
          permitDigest, permitRevision, permitExpiry, now,
          missingRequired, decision, committed>>

Init ==
    /\ authorityRevision = 1
    /\ authorizedDigest = NoDigest
    /\ issued = {}
    /\ consumed = {}
    /\ permitDigest = [p \in Permits |-> NoDigest]
    /\ permitRevision = [p \in Permits |-> 0]
    /\ permitExpiry = [p \in Permits |-> 0]
    /\ now = 0
    /\ missingRequired = FALSE
    /\ decision = "NONE"
    /\ committed = <<>>

Grant(d) ==
    /\ d \in Digests
    /\ authorityRevision < MaxRevision
    /\ authorityRevision' = authorityRevision + 1
    /\ authorizedDigest' = d
    /\ UNCHANGED <<issued, consumed, permitDigest, permitRevision,
                    permitExpiry, now, missingRequired, decision, committed>>

Revoke ==
    /\ authorityRevision < MaxRevision
    /\ authorityRevision' = authorityRevision + 1
    /\ authorizedDigest' = NoDigest
    /\ UNCHANGED <<issued, consumed, permitDigest, permitRevision,
                    permitExpiry, now, missingRequired, decision, committed>>

MarkRequiredInfoMissing ==
    /\ missingRequired' = TRUE
    /\ decision' = "DENY"
    /\ UNCHANGED <<authorityRevision, authorizedDigest, issued, consumed,
                    permitDigest, permitRevision, permitExpiry, now, committed>>

RestoreRequiredInfo ==
    /\ missingRequired' = FALSE
    /\ decision' = "NONE"
    /\ UNCHANGED <<authorityRevision, authorizedDigest, issued, consumed,
                    permitDigest, permitRevision, permitExpiry, now, committed>>

Authorize(p, d) ==
    /\ p \in Permits
    /\ d \in Digests
    /\ p \notin issued
    /\ ~missingRequired
    /\ authorizedDigest = d
    /\ issued' = issued \cup {p}
    /\ permitDigest' = [permitDigest EXCEPT ![p] = d]
    /\ permitRevision' = [permitRevision EXCEPT ![p] = authorityRevision]
    /\ permitExpiry' = [permitExpiry EXCEPT ![p] = now + PermitTTL]
    /\ decision' = "ALLOW"
    /\ UNCHANGED <<authorityRevision, authorizedDigest, consumed, now,
                    missingRequired, committed>>

Execute(p, d) ==
    /\ p \in issued
    /\ p \notin consumed
    /\ d \in Digests
    /\ ~missingRequired
    /\ permitDigest[p] = d
    /\ permitRevision[p] = authorityRevision
    /\ authorizedDigest = d
    /\ now < permitExpiry[p]
    /\ consumed' = consumed \cup {p}
    /\ authorizedDigest' = NoDigest
    /\ committed' = Append(committed,
          [permit |-> p,
           digest |-> d,
           permitRevision |-> permitRevision[p],
           commitRevision |-> authorityRevision,
           viaGateway |-> TRUE,
           completeInfo |-> ~missingRequired,
           unexpired |-> now < permitExpiry[p]])
    /\ UNCHANGED <<authorityRevision, issued, permitDigest, permitRevision,
                    permitExpiry, now, missingRequired, decision>>

Tick ==
    /\ now < MaxTime
    /\ now' = now + 1
    /\ UNCHANGED <<authorityRevision, authorizedDigest, issued, consumed,
                    permitDigest, permitRevision, permitExpiry,
                    missingRequired, decision, committed>>

Next ==
    \/ \E d \in Digests : Grant(d)
    \/ Revoke
    \/ MarkRequiredInfoMissing
    \/ RestoreRequiredInfo
    \/ \E p \in Permits, d \in Digests : Authorize(p, d)
    \/ \E p \in Permits, d \in Digests : Execute(p, d)
    \/ Tick

Spec == Init /\ [][Next]_vars

TypeOK ==
    /\ authorityRevision \in 1..MaxRevision
    /\ authorizedDigest \in Digests \cup {NoDigest}
    /\ issued \subseteq Permits
    /\ consumed \subseteq issued
    /\ permitDigest \in [Permits -> Digests \cup {NoDigest}]
    /\ permitRevision \in [Permits -> 0..MaxRevision]
    /\ permitExpiry \in [Permits -> Nat]
    /\ now \in 0..MaxTime
    /\ missingRequired \in BOOLEAN
    /\ decision \in {"NONE", "ALLOW", "DENY"}

FreshAuthorityAtCommit ==
    \A i \in 1..Len(committed) :
        committed[i].permitRevision = committed[i].commitRevision

ExactEffectBinding ==
    \A i \in 1..Len(committed) :
        committed[i].digest = permitDigest[committed[i].permit]

OneShotPermit ==
    /\ Cardinality(consumed) = Len(committed)
    /\ \A i, j \in 1..Len(committed) :
          i # j => committed[i].permit # committed[j].permit

LogicalGatewayExclusivity ==
    \A i \in 1..Len(committed) : committed[i].viaGateway

FailClosedOnMissingRequiredInfo ==
    /\ missingRequired => decision # "ALLOW"
    /\ \A i \in 1..Len(committed) : committed[i].completeInfo

NoExpiredPermitCommit ==
    \A i \in 1..Len(committed) : committed[i].unexpired

====
