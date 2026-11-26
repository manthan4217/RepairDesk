# RepairDesk – Database Backup, Recovery & Disaster Recovery SOP

This Standard Operating Procedure (SOP) defines the operational guidelines for executing, validating, and restoring database backups for RepairDesk in production environments running MySQL 8.0 (InnoDB engine).

---

## 1. Production Architecture Overview

* **Database Engine:** MySQL 8.0+ / MariaDB 10.6+
* **Storage Engine:** InnoDB (Strict ACID compliance, foreign keys, row-level locking)
* **Default Character Set:** `utf8mb4` (collation `utf8mb4_0900_ai_ci` or `utf8mb4_unicode_ci`)
* **SQL Mode:** `STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO`
* **Connection Pooling:** `CONN_MAX_AGE = 60` (or managed connection pooler such as ProxySQL)

---

## 2. Daily Automated Logical Backup

RepairDesk utilizes transactional, non-blocking logical dumps via `mysqldump`. Because all application tables utilize the InnoDB storage engine, the `--single-transaction` flag enables online backups without locking tables or interrupting active technician operations.

> [!WARNING]
> **Never pass passwords directly on the command-line interface** (e.g. `--password="secret"` or `-psecret`). Doing so exposes credentials in system process tables (`ps aux`, `/proc/<pid>/cmdline`), shell histories, and system logs. Use **MySQL Login Paths** (`mysql_config_editor`) or isolated environment variables (`MYSQL_PWD`).

### 2.1. Primary Recommended Approach: MySQL Encrypted Login Path

MySQL 8.0 provides `mysql_config_editor` to store obfuscated authentication credentials in a protected `.mylogin.cnf` file (permissions `600`).

1. **One-Time Setup:**
   ```bash
   mysql_config_editor set --login-path=repairdesk_backup \
     --host="${DB_HOST:-127.0.0.1}" \
     --port="${DB_PORT:-3306}" \
     --user="${DB_USER}" \
     --password
   # Enter password securely when prompted.
   ```

2. **Execute Non-Blocking Backup:**
   ```bash
   mysqldump \
     --login-path=repairdesk_backup \
     --single-transaction \
     --quick \
     --routines \
     --triggers \
     --hex-blob \
     --default-character-set=utf8mb4 \
     "${DB_NAME:-repairdesk_db}" | gzip -9 > "repairdesk_backup_$(date +%Y%m%d_%H%M%S).sql.gz"
   ```

### 2.2. Alternative Automated Pipeline Approach: Scoped Environment Variable

When running in automated CI/CD runners or container environments where interactive login paths cannot be pre-configured, pass credentials via `MYSQL_PWD` and immediately unset the variable upon completion:

```bash
export MYSQL_PWD="${DB_PASSWORD}"
mysqldump \
  --host="${DB_HOST:-127.0.0.1}" \
  --port="${DB_PORT:-3306}" \
  --user="${DB_USER}" \
  --single-transaction \
  --quick \
  --routines \
  --triggers \
  --hex-blob \
  --default-character-set=utf8mb4 \
  "${DB_NAME:-repairdesk_db}" | gzip -9 > "repairdesk_backup_$(date +%Y%m%d_%H%M%S).sql.gz"
unset MYSQL_PWD
```

### 2.3. Explanation of Essential Flags

| Flag | Purpose |
| :--- | :--- |
| `--single-transaction` | Sets transaction isolation to `REPEATABLE READ` before dumping; ensures consistent snapshot without locking tables. |
| `--quick` | Forces mysqldump to stream rows from the server row-by-row rather than buffering entire tables in memory. |
| `--routines --triggers` | Includes stored procedures, functions, and database triggers. |
| `--hex-blob` | Dumps binary data in hexadecimal notation to prevent corruption of encoded payloads. |
| `--default-character-set=utf8mb4` | Ensures multilingual text, customer notes, and technical symbols are preserved. |

---

## 3. Automated Scheduling Examples

### 3.1. Linux / Crontab (Daily at 02:00 AM)

Create `/opt/repairdesk/scripts/backup_db.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="/var/backups/repairdesk"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
OUTPUT_FILE="${BACKUP_DIR}/repairdesk_backup_${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

# Execute non-blocking backup using encrypted login-path or scoped MYSQL_PWD
if mysql_config_editor print --login-path=repairdesk_backup >/dev/null 2>&1; then
    mysqldump --login-path=repairdesk_backup \
      --single-transaction --quick --routines --triggers --hex-blob \
      --default-character-set=utf8mb4 "${DB_NAME:-repairdesk_db}" | gzip -9 > "${OUTPUT_FILE}"
else
    export MYSQL_PWD="${DB_PASSWORD}"
    mysqldump -h "${DB_HOST:-127.0.0.1}" -P "${DB_PORT:-3306}" -u "${DB_USER}" \
      --single-transaction --quick --routines --triggers --hex-blob \
      --default-character-set=utf8mb4 "${DB_NAME:-repairdesk_db}" | gzip -9 > "${OUTPUT_FILE}"
    unset MYSQL_PWD
fi

# Retain daily backups for 30 days
find "${BACKUP_DIR}" -type f -name "repairdesk_backup_*.sql.gz" -mtime +30 -delete
```

Create `/etc/cron.d/repairdesk_backup`:
```cron
0 2 * * * repairdesk /opt/repairdesk/scripts/backup_db.sh >> /var/log/repairdesk_backup.log 2>&1
```

### 3.2. Windows Task Scheduler / PowerShell

Create `scripts\backup_database.ps1`:
```powershell
# Requires 7-Zip (7z.exe) in PATH for streaming compression
$ErrorActionPreference = "Stop"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir = "C:\Backups\RepairDesk"
$OutputFile = "$BackupDir\repairdesk_backup_$Timestamp.sql.gz"

if (!(Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir -Force
}

try {
    # Scoped credential passing without command-line exposure
    $env:MYSQL_PWD = $env:DB_PASSWORD
    & mysqldump.exe -h $env:DB_HOST -P $env:DB_PORT -u $env:DB_USER `
        --single-transaction --quick --routines --triggers --hex-blob `
        --default-character-set=utf8mb4 $env:DB_NAME | 7z a -si $OutputFile
}
finally {
    # Ensure credentials are purged from process memory
    Remove-Item Env:\MYSQL_PWD -ErrorAction SilentlyContinue
}

# Retain backups for 30 days
Get-ChildItem -Path $BackupDir -Filter "*.sql.gz" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
    Remove-Item -Force
```

---

## 4. Database Restoration Procedure

> [!CAUTION]
> Restoring a database will overwrite existing tables and service history. Always verify the target environment before executing.

### 4.1. Step-by-Step Restoration

1. **Verify Backup Integrity:**
   ```bash
   gzip -t repairdesk_backup_YYYYMMDD_HHMMSS.sql.gz
   ```

2. **Prepare Clean Database (or Staging Database):**
   ```bash
   mysql -u root -p -e "DROP DATABASE IF EXISTS repairdesk_db; CREATE DATABASE repairdesk_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
   ```

3. **Restore Data Stream:**
   ```bash
   # Option A: Interactive password prompt (recommended for manual disaster recovery)
   gunzip < repairdesk_backup_YYYYMMDD_HHMMSS.sql.gz | mysql -h "${DB_HOST:-127.0.0.1}" -P "${DB_PORT:-3306}" -u "${DB_USER}" -p "${DB_NAME:-repairdesk_db}"

   # Option B: Automated pipeline restore via scoped MYSQL_PWD (no command-line exposure)
   export MYSQL_PWD="${DB_PASSWORD}"
   gunzip < repairdesk_backup_YYYYMMDD_HHMMSS.sql.gz | mysql -h "${DB_HOST:-127.0.0.1}" -P "${DB_PORT:-3306}" -u "${DB_USER}" "${DB_NAME:-repairdesk_db}"
   unset MYSQL_PWD
   ```

4. **Verify Application Schema & Migrations:**
   ```bash
   python manage.py showmigrations
   python manage.py migrate --check
   ```

5. **Execute Integrity Sanity Checks:**
   ```bash
   python manage.py test apps.tickets.test_database_integrity
   ```

---

## 5. Point-in-Time Recovery (PITR) with Binary Logs

For mission-critical production installations where data loss between backups must be near zero:
1. Ensure `log_bin = /var/log/mysql/mysql-bin.log` and `binlog_format = ROW` are enabled in `my.cnf`.
2. To restore to an exact timestamp (e.g., prior to an accidental data modification at `2026-11-24 15:30:00`):
   * Restore the last nightly backup as detailed above.
   * Apply incremental binary logs up to the stop position:
     ```bash
     mysqlbinlog --stop-datetime="2026-11-24 15:29:59" /var/log/mysql/mysql-bin.000* | mysql -u root -p repairdesk_db
     ```

---

## 6. Retention and Verification Schedule

* **Retention Policy:**
  * Daily backups retained for 30 days.
  * Weekly full snapshots retained for 12 weeks.
  * Monthly archives retained for 1 year off-site (e.g., AWS S3 / Azure Blob Storage with immutability/WORM enabled).
* **Restoration Drills:**
  * Drill restoration to a staging environment once per quarter to confirm backup viability and measure Recovery Time Objective (RTO < 30 minutes).
