import json
import os
import subprocess
import sys


def load_env_password():
    if os.getenv("SQL_SERVER_PASSWORD"):
        return os.getenv("SQL_SERVER_PASSWORD")
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip().startswith("SQL_SERVER_PASSWORD="):
                    return line.strip().split("=", 1)[1].strip()
    raise SystemExit("SQL_SERVER_PASSWORD not set in environment or root .env")


def run(cmd):
    res = subprocess.run(cmd, text=True, capture_output=True, check=False)
    return res.returncode, res.stdout.strip(), res.stderr.strip()


def check_mongo():
    js = """
    const summary = {
      LocationDB: {
        LiveLocations: db.getSiblingDB('LocationDB').LiveLocations.countDocuments({}),
        AVAILABLE: db.getSiblingDB('LocationDB').LiveLocations.countDocuments({status: 'AVAILABLE'}),
        BUSY: db.getSiblingDB('LocationDB').LiveLocations.countDocuments({status: 'BUSY'}),
        OFFLINE: db.getSiblingDB('LocationDB').LiveLocations.countDocuments({status: 'OFFLINE'}),
      },
      MatchingDB: {
        ProcessedTrips: db.getSiblingDB('MatchingDB').ProcessedTrips.countDocuments({}),
        FinishedTrips: db.getSiblingDB('MatchingDB').FinishedTrips.countDocuments({}),
        MatchingResults: db.getSiblingDB('MatchingDB').MatchingResults.countDocuments({}),
      },
      DataWarehouseDB: {
        Fact_Events: db.getSiblingDB('DataWarehouseDB').Fact_Events.countDocuments({}),
        DeadLetterQueue: db.getSiblingDB('DataWarehouseDB').DeadLetterQueue.countDocuments({}),
      }
    };
    print(JSON.stringify(summary, null, 2));
    """
    code, out, err = run(["docker", "compose", "exec", "-T", "mongodb", "mongosh", "--quiet", "--eval", js])
    if code != 0:
        print(f"[MongoDB ERROR] {err}", file=sys.stderr)
        return
    print("=== MongoDB (LocationDB, MatchingDB, DataWarehouseDB) ===")
    print(out)


def check_sqlserver(password):
    query = (
        "SET NOCOUNT ON; "
        "SELECT 'IdentityDB.Users' AS TableName, COUNT(*) AS Cnt FROM IdentityDB.dbo.Users "
        "UNION ALL SELECT 'IdentityDB.Vehicles', COUNT(*) FROM IdentityDB.dbo.Vehicles "
        "UNION ALL SELECT 'BookingDB.Trips', COUNT(*) FROM BookingDB.dbo.Trips "
        "UNION ALL SELECT 'BookingDB.Idempotency_Log', COUNT(*) FROM BookingDB.dbo.Idempotency_Log;"
    )
    sqlcmd_paths = ["/opt/mssql-tools18/bin/sqlcmd", "/opt/mssql-tools/bin/sqlcmd"]
    for bin_path in sqlcmd_paths:
        code, out, err = run([
            "docker", "compose", "exec", "-T", "sqlserver",
            bin_path, "-S", "localhost", "-U", "sa", "-P", password, "-C", "-Q", query,
        ])
        if code == 0:
            print("=== SQL Server (IdentityDB, BookingDB) ===")
            print(out)
            return
    print(f"[SQL Server ERROR] Could not query IdentityDB/BookingDB via sqlcmd: {err}", file=sys.stderr)


if __name__ == "__main__":
    check_sqlserver(load_env_password())
    check_mongo()
