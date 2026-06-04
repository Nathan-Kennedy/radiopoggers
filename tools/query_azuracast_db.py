#!/usr/bin/env python3
import subprocess
import sys

sql = sys.argv[1] if len(sys.argv) > 1 else "SELECT id, name FROM station_playlists;"
script = f"mariadb -N -B -h localhost -u $MYSQL_USER -p$MYSQL_PASSWORD $MYSQL_DATABASE -e {sql!r}"
result = subprocess.run(
    ["docker", "exec", "azuracast", "bash", "-lc", script],
    capture_output=True,
    text=True,
)
print(result.stdout)
if result.stderr:
    print(result.stderr, file=sys.stderr)
raise SystemExit(result.returncode)
