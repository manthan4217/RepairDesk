# RepairDesk – Phase 5, Batch 6.2: Isolated MySQL Backup & Restore Drill Report

- **Report Date:** 2026-11-26
- **Environment:** MySQL Server 8.0.46 (Win64) Community Server, Python 3.13.1, Django 5.2.19, `mysqlclient==2.3.2`
- **Host / Port:** `127.0.0.1:3306`
- **Source Database:** `repairdesk_test_db`
- **Existing Test Database:** `test_repairdesk_test_db`
- **Target Staging Database:** `repairdesk_restore_drill_db`
- **Audit Status:** **PASS** (End-to-End Backup & Restore Verified)

---

## 1. Executive Summary

As part of Phase 5, Batch 6.2, an isolated end-to-end database backup and restore verification drill was executed against the local MySQL 8.0.46 database instance.

A full transactional, non-blocking logical dump of the active application database (`repairdesk_test_db`) was generated strictly adhering to the standard operating procedures defined in [docs/database_backup_restore.md](file:///c:/Users/manth/OneDrive/Desktop/RepairDesk/docs/database_backup_restore.md). The resulting backup was streamed into an isolated staging database (`repairdesk_restore_drill_db`).

Comprehensive comparative schema audits, row-count verifications, foreign key and index checks, native MySQL 8.0 `CHECK` constraint tests, and read-only Django connection tests confirmed **100% schema and data fidelity**. The two existing databases (`repairdesk_test_db` and `test_repairdesk_test_db`) were kept completely isolated and untouched.

---

## 2. Backup Execution & Artifact Details

### 2.1. Backup Parameters
- **Utility:** `C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe` (Ver 8.0.46 for Win64)
- **Options Used:**
  ```bash
  mysqldump \
    --host=127.0.0.1 \
    --port=3306 \
    --user=repairdesk_user \
    --single-transaction \
    --quick \
    --routines \
    --triggers \
    --hex-blob \
    --default-character-set=utf8mb4 \
    repairdesk_test_db
  ```
- **Credential Protection:** Credentials were provided strictly in process memory via the `MYSQL_PWD` environment variable within Python subprocess isolation. No passwords appeared in process arguments, shell history, terminal logs, or Git history.
- **Git Ignore Protection:** Saved to local directory `backups/`, verified Git-ignored via [.gitignore](file:///c:/Users/manth/OneDrive/Desktop/RepairDesk/.gitignore#L3).

### 2.2. Generated Artifacts

| Artifact | Path | Size (Bytes) | SHA-256 Checksum |
| :--- | :--- | :--- | :--- |
| **SQL Dump** | `backups/repairdesk_backup_20261126_211041.sql` | 30,945 bytes | `a3f1ca8a75af2fca347e15198c0d08b4595cf67d98c984e883b8ec54a076a81c` |
| **Gzip Archive** | `backups/repairdesk_backup_20261126_211041.sql.gz` | 4,690 bytes | `fa2606100bc93c6ec942d39adf99175f942083f2277e5247a6cad15a1dfd2be8` |

- **Integrity Inspection:** 597 lines of valid MySQL DDL and DML. Confirmed presence of all 18 application tables, table structures, `utf8mb4` character set definitions, and migration data.

---

## 3. Staging Database Provisioning & Restoration

### 3.1. Staging Database Creation
- **Database Name:** `repairdesk_restore_drill_db`
- **Initial State:** Verified to not exist prior to drill; provisioned using MySQL root with:
  ```sql
  CREATE DATABASE repairdesk_restore_drill_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
  GRANT ALL PRIVILEGES ON repairdesk_restore_drill_db.* TO 'repairdesk_user'@'127.0.0.1';
  FLUSH PRIVILEGES;
  ```
- **Pre-Restore State:** 0 tables present; character set `utf8mb4`, collation `utf8mb4_unicode_ci`.

### 3.2. Restore Execution
- **Utility:** `C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe` (Ver 8.0.46 for Win64)
- **Command:**
  ```bash
  mysql --host=127.0.0.1 --port=3306 --user=repairdesk_user --default-character-set=utf8mb4 repairdesk_restore_drill_db < backups/repairdesk_backup_20261126_211041.sql
  ```
- **Exit Code:** `0` (Success)
- **Duration:** `2.073` seconds
- **Errors / Warnings:** None

---

## 4. Database Metadata & Schema Comparison

Comparative audit executed across `information_schema` querying source database `repairdesk_test_db` against restored staging database `repairdesk_restore_drill_db`:

### 4.1. Table Structure & Storage Engine Comparison

| Table Name | Source Engine | Restored Engine | Source Collation | Restored Collation | Match |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `accounts_user` | InnoDB | InnoDB | `utf8mb4_unicode_ci` | `utf8mb4_unicode_ci` | Identical |
| `accounts_user_groups` | InnoDB | InnoDB | `utf8mb4_unicode_ci` | `utf8mb4_unicode_ci` | Identical |
| `accounts_user_user_permissions` | InnoDB | InnoDB | `utf8mb4_unicode_ci` | `utf8mb4_unicode_ci` | Identical |
| `auth_group` | InnoDB | InnoDB | `utf8mb4_unicode_ci` | `utf8mb4_unicode_ci` | Identical |
| `auth_group_permissions` | InnoDB | InnoDB | `utf8mb4_unicode_ci` | `utf8mb4_unicode_ci` | Identical |
| `auth_permission` | InnoDB | InnoDB | `utf8mb4_unicode_ci` | `utf8mb4_unicode_ci` | Identical |
| `customers_customer` | InnoDB | InnoDB | `utf8mb4_unicode_ci` | `utf8mb4_unicode_ci` | Identical |
| `customers_device` | InnoDB | InnoDB | `utf8mb4_unicode_ci` | `utf8mb4_unicode_ci` | Identical |
| `django_admin_log` | InnoDB | InnoDB | `utf8mb4_unicode_ci` | `utf8mb4_unicode_ci` | Identical |
| `django_content_type` | InnoDB | InnoDB | `utf8mb4_unicode_ci` | `utf8mb4_unicode_ci` | Identical |
| `django_migrations` | InnoDB | InnoDB | `utf8mb4_unicode_ci` | `utf8mb4_unicode_ci` | Identical |
| `django_session` | InnoDB | InnoDB | `utf8mb4_unicode_ci` | `utf8mb4_unicode_ci` | Identical |
| `tickets_assignment` | InnoDB | InnoDB | `utf8mb4_unicode_ci` | `utf8mb4_unicode_ci` | Identical |
| `tickets_attachment` | InnoDB | InnoDB | `utf8mb4_unicode_ci` | `utf8mb4_unicode_ci` | Identical |
| `tickets_completionreport` | InnoDB | InnoDB | `utf8mb4_unicode_ci` | `utf8mb4_unicode_ci` | Identical |
| `tickets_repairupdate` | InnoDB | InnoDB | `utf8mb4_unicode_ci` | `utf8mb4_unicode_ci` | Identical |
| `tickets_serviceticket` | InnoDB | InnoDB | `utf8mb4_unicode_ci` | `utf8mb4_unicode_ci` | Identical |
| `tickets_statushistory` | InnoDB | InnoDB | `utf8mb4_unicode_ci` | `utf8mb4_unicode_ci` | Identical |

- **Table Count:** **18 source vs 18 restored** (100% match)
- **Engine Consistency:** **18/18 InnoDB** (100% match)
- **Collation Consistency:** **18/18 `utf8mb4_unicode_ci`** (100% match)

### 4.2. Row Count Verification

| Table Name | Source Row Count | Restored Row Count | Variance |
| :--- | :--- | :--- | :--- |
| `accounts_user` | 0 | 0 | 0 |
| `accounts_user_groups` | 0 | 0 | 0 |
| `accounts_user_user_permissions` | 0 | 0 | 0 |
| `auth_group` | 0 | 0 | 0 |
| `auth_group_permissions` | 0 | 0 | 0 |
| `auth_permission` | 56 | 56 | 0 |
| `customers_customer` | 0 | 0 | 0 |
| `customers_device` | 0 | 0 | 0 |
| `django_admin_log` | 0 | 0 | 0 |
| `django_content_type` | 14 | 14 | 0 |
| `django_migrations` | 25 | 25 | 0 |
| `django_session` | 0 | 0 | 0 |
| `tickets_assignment` | 0 | 0 | 0 |
| `tickets_attachment` | 0 | 0 | 0 |
| `tickets_completionreport` | 0 | 0 | 0 |
| `tickets_repairupdate` | 0 | 0 | 0 |
| `tickets_serviceticket` | 0 | 0 | 0 |
| `tickets_statushistory` | 0 | 0 | 0 |

- **Total Non-Migration Records:** 70 records (56 permissions + 14 content types) exactly restored.
- **Application Tables:** 0 records (confirmed unpolluted in both source and restored).

### 4.3. Constraints and Indexes Comparison

| Metric | Source (`repairdesk_test_db`) | Restored (`repairdesk_restore_drill_db`) | Match |
| :--- | :--- | :--- | :--- |
| **Foreign Keys** | 25 | 25 | Identical (100%) |
| **Total Index Definitions** | 59 | 59 | Identical (100%) |
| **MySQL 8.0 CHECK Constraints**| 5 | 5 | Identical (100%) |

**Restored MySQL CHECK Constraints in `information_schema.check_constraints`:**
1. `accounts_user_role_valid`: ``(`role` in ('administrator', 'technician'))``
2. `django_admin_log_chk_1`: ``(`action_flag` >= 0)``
3. `ticket_priority_valid`: ``(`priority` in ('low', 'normal', 'high', 'urgent'))``
4. `ticket_status_valid`: ``(`status` in ('received', 'under_diagnosis', 'in_progress', 'on_hold', 'completed', 'ready_for_delivery', 'delivered', 'cancelled'))``
5. `ticket_estimated_cost_non_negative`: ``((`estimated_cost` >= 0) or (`estimated_cost` is null))``

### 4.4. Active Enforcement Validation on Restored Staging Database
Direct SQL violation tests executed against `repairdesk_restore_drill_db`:
- **CHECK Constraint Enforcement Test:** Inserting invalid status `'invalid_status'` raised `MySQLdb.OperationalError: (3819, "Check constraint 'ticket_status_valid' is violated.")`. **PASS**.
- **Foreign Key Enforcement Test:** Inserting invalid foreign key `created_by_id=9999` raised `MySQLdb.IntegrityError: (1452, "Cannot add or update a child row: a foreign key constraint fails...")`. **PASS**.

---

## 5. Django Verification Against Restored Staging Database

Executed read-only verification by passing `DB_NAME=repairdesk_restore_drill_db` via isolated process environment:

1. **Connection & Vendor Test:**
   - `connection.vendor`: `mysql`
   - Connected Database: `repairdesk_restore_drill_db`
   - `SELECT VERSION()`: `8.0.46`
2. **Django ORM Model Querying:**
   - `User.objects.count()`: `0`
   - `Customer.objects.count()`: `0`
   - `Device.objects.count()`: `0`
   - `ServiceTicket.objects.count()`: `0`
3. **Django System Health Check:**
   - `python manage.py check`:
     ```
     System check identified no issues (0 silenced).
     ```
4. **Django Migration Status Check:**
   - `python manage.py showmigrations`:
     All **25/25 migrations** recognized as applied (`[X]`), 0 unapplied.

---

## 6. Safety & Isolation Audit

- **Application Database (`repairdesk_test_db`):** Verified intact with 18 tables and 0 application records.
- **Automated Test Database (`test_repairdesk_test_db`):** Verified intact with 18 tables.
- **Git Status:** Backup files (`backups/`) and local credentials remain untracked. No git commit or push operations performed.

---

## 7. Cleanup Recommendation

- **Staging Database (`repairdesk_restore_drill_db`):** Retained intact as requested for stakeholder inspection.
- **Post-Inspection Safe Removal:** Once reviewed, the staging database can be safely dropped by executing:
  ```sql
  DROP DATABASE repairdesk_restore_drill_db;
  ```
- **Backup File:** Retained in `backups/repairdesk_backup_20261126_211041.sql` (and `.sql.gz`) as permanent evidence of drill completion.

---

## 8. Final Assessment

### Overall Result: **PASS**

The backup and recovery SOP documented in [docs/database_backup_restore.md](file:///c:/Users/manth/OneDrive/Desktop/RepairDesk/docs/database_backup_restore.md) is verified to produce fully valid, structurally complete, non-locking, and recoverable backups on MySQL 8.0.46. All schema objects, InnoDB storage engines, character sets, check constraints, foreign keys, and Django migration states are preserved with 100% fidelity upon restoration.
