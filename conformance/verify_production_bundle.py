"""Offline production evidence verifier. Exit 0 only on independently proven PASS."""
import argparse
import json
import sys
from pathlib import Path
from production_proof import verify_directory

def main():
    p=argparse.ArgumentParser()
    p.add_argument('bundle',help='directory containing evidence JSON artifacts')
    p.add_argument('--trust-store',required=True,help='JSON mapping key_id to base64 Ed25519 public key')
    args=p.parse_args()
    try:
        keys=json.loads(Path(args.trust_store).read_text())
        result=verify_directory(args.bundle,keys)
    except (OSError,ValueError,TypeError) as exc:
        result={'status':'INCOMPLETE','reason':'unreadable evidence or trust store','detail':str(exc)}
    print(json.dumps(result,indent=2))
    return 0 if result['status']=='PASS' else 1

if __name__=='__main__':sys.exit(main())
