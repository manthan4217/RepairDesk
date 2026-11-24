# RepairDesk

## Service & Repair Management Platform

> **Project status:** Planning / specification baseline\
> **Project type:** Django-based web application\
> **Primary goal:** Organise the complete service and repair lifecycle
> in one place.

------------------------------------------------------------------------

## 1. Project Overview

RepairDesk is a web-based Service and Repair Management Platform
intended to help repair and service businesses manage customers, devices
or equipment, service requests, repair jobs, technicians, repair
progress and service history.

The platform replaces scattered paper registers, spreadsheets and
informal communication with a centralised digital workflow.
Administrators can register customers and items received for service,
create uniquely numbered repair tickets, assign technicians, monitor
progress and review completed work. Technicians can view assigned jobs,
record diagnosis and repair notes, update job status and submit
completion reports. Customers may use a customer portal to submit
requests and check progress, subject to the final MVP decision.

The initial implementation should focus on a clearly defined
repair-business workflow. The underlying design may be extendable to
other repair categories later, but the first release should not attempt
to support every industry-specific process.

### One-line description

**RepairDesk helps repair businesses register service requests, assign
technicians, track repairs and maintain reliable service records through
a single digital platform.**

------------------------------------------------------------------------

## 2. Problem Statement

Many small and medium repair businesses manage service work through
paper forms, notebooks, spreadsheets, phone calls or messaging
applications. This can lead to:

-   Customer and device details being recorded inconsistently.
-   Difficulty locating the current status of a repair.
-   Unclear responsibility for a repair job.
-   Missing diagnosis, parts and completion records.
-   Repeated calls to ask for repair updates.
-   Difficulty reviewing technician workload and pending jobs.
-   No dependable, searchable service history.

RepairDesk aims to provide a structured process and a shared source of
accurate repair information.

## 3. Project Objectives

1.  Digitise customer and device/equipment registration.
2.  Create a unique service ticket for each repair request.
3.  Provide a clear repair lifecycle and status history.
4.  Allow administrators to assign work to technicians.
5.  Allow technicians to record diagnosis, work performed and completion
    details.
6.  Maintain customer, device and repair history.
7.  Provide an administrative dashboard for operational visibility.
8.  Validate user input and protect information through authentication
    and role-based access.
9.  Deliver a responsive interface suitable for desktop, tablet and
    mobile screens.
10. Build the application using maintainable Django conventions and
    version control.

------------------------------------------------------------------------

## 4. Product Scope

### 4.1 Proposed initial customer segment

**Working assumption:** independent computer/laptop repair shops and
small service centres.

This is a proposed starting segment, not a confirmed market decision.
Confirm it through discussions with actual repair businesses before
finalising specialised fields and workflows.

### 4.2 In scope for the first working MVP

-   Authentication and role-based access.
-   Admin dashboard.
-   Customer management.
-   Device/equipment registration.
-   Service ticket creation and ticket number generation.
-   Technician management.
-   Technician assignment.
-   Repair diagnosis and notes.
-   Repair status tracking.
-   Completion report.
-   Service history.
-   Basic operational reports.
-   Responsive interface.
-   Django Admin integration where useful.

### 4.3 Proposed later enhancements

-   Customer self-service portal.
-   Customer notifications by email or SMS.
-   Spare-parts inventory and stock movements.
-   Estimates and customer approval.
-   Invoice generation and payment tracking.
-   Warranty tracking.
-   Pickup and delivery tracking.
-   Advanced analytics and exports.
-   Multiple branches and organisation-level tenancy.
-   Technician mobile PWA with offline support.

These items are not automatically part of the first MVP. Prioritise only
after the core repair workflow is working and tested.

### 4.4 Out of scope until separately approved

-   Native Android and iOS applications.
-   Payment gateway integration.
-   Live technician GPS tracking.
-   AI-based diagnosis or repair recommendations.
-   Complex accounting or ERP functionality.
-   IoT integrations.

------------------------------------------------------------------------

## 5. Main User Roles

The exact permissions should be finalised before implementation. The
following is the proposed baseline.

  -----------------------------------------------------------------------
  Role                                Responsibilities
  ----------------------------------- -----------------------------------
  Administrator / Owner               Manages users, customers, devices,
                                      tickets, assignments, settings and
                                      reports.

  Technician                          Views assigned jobs, records
                                      diagnosis, updates permitted
                                      statuses and submits repair
                                      reports.

  Customer                            Optional MVP role; submits service
                                      requests and views only their own
                                      requests and updates.
  -----------------------------------------------------------------------

### Permission principles

-   A user must sign in before accessing protected application pages.
-   Technicians must not access administrative functions unless
    explicitly authorised.
-   Customers, if enabled, must only see their own records.
-   All permissions must be checked on the server, not only by hiding
    interface elements.
-   Users must not be able to change another user's role or access level
    through a crafted request.
-   Administrative actions should be attributable to the user who
    performed them.

------------------------------------------------------------------------

## 6. End-to-End Working Flow

``` text
Start
  |
  v
Administrator signs in
  |
  v
Register / select customer
  |
  v
Register device or equipment
  |
  v
Create service request
  |
  v
Generate unique repair ticket
  |
  v
Review request and assign technician
  |
  v
Technician views assigned job
  |
  v
Inspect item and record diagnosis
  |
  v
Perform repair and record work
  |
  v
Update repair status
  |
  v
Repair completed?
  |             |
  | No          | Yes
  v             v
Continue work   Submit completion report
  |             |
  +----<        v
           Admin verifies / closes job
                 |
                 v
          Update service history
                 |
                 v
                End
```

### Proposed ticket lifecycle

Use a controlled set of statuses. The final transitions must be enforced
by backend business rules.

  -----------------------------------------------------------------------
  Status                              Meaning
  ----------------------------------- -----------------------------------
  Received                            Item/request has been registered.

  Under Diagnosis                     Technician is inspecting the
                                      reported issue.

  Awaiting Approval                   Estimate or repair approval is
                                      required. Optional until estimates
                                      are implemented.

  In Progress                         Repair work is underway.

  On Hold                             Work cannot continue temporarily; a
                                      reason is required.

  Completed                           Technician has submitted the repair
                                      as complete.

  Ready for Delivery                  Final checks are complete and item
                                      is ready to be returned.

  Delivered / Closed                  Item has been handed over and
                                      ticket is closed.

  Cancelled                           Request was cancelled with a
                                      recorded reason.
  -----------------------------------------------------------------------

Do not allow arbitrary status text. Implement allowed transitions and
record who changed the status, when, and why.

------------------------------------------------------------------------

## 7. Functional Requirements

### FR-01: Authentication

-   Users can sign in and sign out.
-   Registration is restricted to the chosen account-creation policy.
-   Passwords are handled by Django's authentication system; never store
    plain-text passwords.
-   Protected pages require authentication.
-   Invalid credentials produce safe, understandable feedback.
-   Password reset can be added if email delivery is configured.

**Acceptance criteria** - Valid users can sign in and sign out. -
Invalid credentials do not create a session. - Anonymous users cannot
open protected pages. - Passwords are not stored in plain text.

### FR-02: Dashboard

Display useful operational summaries, such as:

-   Total service tickets.
-   Newly received requests.
-   Jobs awaiting assignment.
-   Jobs in progress.
-   Jobs on hold.
-   Completed jobs.
-   Recent ticket activity.

Dashboard counts must be calculated from database records and respect
the signed-in user's permissions.

### FR-03: Customer Management

Administrators can:

-   Create a customer record.
-   View customer details.
-   Update customer contact details.
-   Search customers.
-   View a customer's repair history.
-   Deactivate or archive a customer where appropriate.

Suggested fields:

-   Customer ID.
-   Full name or business name.
-   Phone number.
-   Email address (optional if not available).
-   Address (only if needed).
-   Created date.
-   Active/inactive status.

Validate phone and email formats sensibly. Avoid collecting personal
information that the workflow does not need.

### FR-04: Device / Equipment Management

Record the item submitted for repair.

Suggested fields:

-   Device/equipment ID.
-   Customer.
-   Item category.
-   Brand.
-   Model.
-   Serial number or other identifier (optional where unavailable).
-   Physical condition at intake.
-   Accessories received.
-   Customer-reported issue.
-   Intake date.
-   Relevant notes.

A customer may have multiple devices. A device may have multiple service
tickets over time.

### FR-05: Service Request / Ticket Management

-   Create a ticket linked to a customer and device/equipment.
-   Generate a unique, human-readable ticket number.
-   Record reported problem, intake date and priority.
-   View, search and filter tickets.
-   Edit permitted ticket details.
-   Prevent duplicate ticket numbers.
-   Record ticket creation and update timestamps.

Example ticket format: `RD-2026-00001`. This is illustrative; implement
a collision-safe generation method rather than relying only on a count.

### FR-06: Technician Management

-   Add and update technician profiles.
-   Activate or deactivate technicians.
-   View assigned and open jobs.
-   Store only necessary contact and employment information.
-   Restrict technician records to authorised administrators.

### FR-07: Job Assignment

-   Assign a ticket to a technician.
-   Reassign a job when authorised.
-   Show the assigned technician and assignment date.
-   Prevent assignment to inactive technicians.
-   Preserve assignment history where practical.

### FR-08: Diagnosis and Repair Updates

Technicians can, subject to permissions:

-   View assigned tickets.
-   Record inspection findings.
-   Record diagnosis.
-   Add repair notes and work performed.
-   Record parts used if inventory is implemented.
-   Update status through permitted transitions.
-   Record time spent if required by the pilot business.

### FR-09: Completion Report

A completion report should capture:

-   Diagnosis.
-   Work performed.
-   Parts replaced (if applicable).
-   Final status.
-   Technician remarks.
-   Completion date and time.
-   Technician identity.
-   Optional attachments or images.

A ticket should not be marked delivered/closed until the required
completion and handover steps are satisfied.

### FR-10: Service History

-   Show previous tickets for a customer.
-   Show previous repairs for a device.
-   Show status and date history.
-   Keep completed records available for future reference.
-   Do not silently erase historical records when a customer or device
    is archived.

### FR-11: Search and Filters

Provide useful filters, for example:

-   Ticket number.
-   Customer name.
-   Phone number.
-   Device serial number.
-   Ticket status.
-   Technician.
-   Date range.

Search must be permission-aware and should not reveal records belonging
to another customer or business.

### FR-12: Reports

Initial reports may include:

-   Tickets received in a date range.
-   Tickets by status.
-   Completed versus pending tickets.
-   Technician job allocation.
-   Average time to completion, only when timestamps are reliable.

Reports should be based on actual records. Export formats can be added
after core reports work.

### FR-13: Notifications (later phase unless required)

Potential events:

-   Ticket created.
-   Technician assigned.
-   Status changed.
-   Repair completed.
-   Item ready for collection.

Start with in-app notifications or clear status visibility. External
email/SMS services require configuration, consent and testing.

------------------------------------------------------------------------

## 8. Non-Functional Requirements

### Usability

-   Clear navigation and consistent page layouts.
-   Forms use labels, validation messages and helpful feedback.
-   Common tasks should require minimal unnecessary steps.

### Responsiveness

-   Pages should work on desktop, tablet and mobile screen widths.
-   Tables should remain usable on small screens through responsive
    layouts or alternative card views.

### Performance

-   Paginate long lists.
-   Avoid unnecessary database queries.
-   Add indexes for frequently searched fields after reviewing query
    patterns.

### Reliability

-   Use database transactions for multi-step operations where partial
    updates would corrupt the workflow.
-   Show safe error pages and preserve user-entered data where possible.
-   Back up the database according to the deployment environment's
    policy.

### Maintainability

-   Separate Django apps by business responsibility.
-   Keep views focused; put reusable business logic in appropriate
    service/helper modules.
-   Use meaningful names and comments where they improve understanding.
-   Keep secrets out of source control.

### Accessibility

-   Use semantic HTML.
-   Associate form labels with inputs.
-   Ensure keyboard navigation and visible focus states.
-   Do not rely on colour alone to communicate status.

------------------------------------------------------------------------

## 9. Proposed Technology Stack

  -----------------------------------------------------------------------
  Layer                   Technology              Purpose
  ----------------------- ----------------------- -----------------------
  Programming language    Python                  Application logic

  Backend                 Django                  Web framework, ORM,
                                                  authentication and
                                                  admin

  API                     Django REST Framework   API endpoints if
                                                  frontend/API separation
                                                  is required

  Database                MySQL                   Persistent relational
                                                  data

  Frontend                HTML5, CSS3, JavaScript User interface

  UI framework            Bootstrap               Responsive layout and
                                                  components

  Charts                  Chart.js                Dashboard
                                                  visualisations

  Version control         Git and GitHub          Source history and
                                                  collaboration

  API testing             Postman or equivalent   API request testing

  Development environment Python virtual          Dependency isolation
                          environment             
  -----------------------------------------------------------------------

**Important:** Django templates may be used for the first web interface.
DRF should be introduced for API endpoints needed by a separate client
or technician PWA; do not add API complexity without a use case.

------------------------------------------------------------------------

## 10. Proposed Django Application Structure

A possible structure is shown below. It is a design proposal and can be
adjusted as the implementation develops.

``` text
RepairDesk/
├── manage.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
│
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── apps/
│   ├── accounts/
│   ├── customers/
│   ├── devices/
│   ├── tickets/
│   ├── technicians/
│   ├── repairs/
│   ├── reports/
│   └── notifications/
│
├── templates/
│   ├── base.html
│   ├── accounts/
│   ├── dashboard/
│   ├── customers/
│   ├── devices/
│   ├── tickets/
│   └── repairs/
│
├── static/
│   ├── css/
│   ├── js/
│   └── images/
│
├── media/                 # User uploads; do not commit private uploads
└── docs/
    ├── er-diagram/
    ├── flowcharts/
    ├── screenshots/
    └── project-report/
```

Keep each app responsible for a coherent business area. Avoid putting
the entire project in one `views.py` or one model file.

------------------------------------------------------------------------

## 11. Proposed Database Design

The following is an initial logical design. Final field types,
constraints and relationships must be confirmed during ERD design.

### Core entities

  -----------------------------------------------------------------------
  Entity                  Purpose                 Example important
                                                  fields
  ----------------------- ----------------------- -----------------------
  User                    Login identity          id, username/email,
                                                  password hash,
                                                  is_active

  UserProfile             Additional user details user_id, display_name,
                                                  phone

  Customer                Customer record         id, name, phone, email,
                                                  address

  Device                  Customer-owned          id, customer_id,
                          repairable item         category, brand, model,
                                                  serial_number

  TechnicianProfile       Technician details      id, user_id, active

  ServiceTicket           Repair request          id, ticket_number,
                                                  customer_id, device_id,
                                                  issue, priority,
                                                  status, created_at

  Assignment              Technician assignment   id, ticket_id,
                          history                 technician_id,
                                                  assigned_by_id,
                                                  assigned_at

  RepairUpdate            Diagnosis and progress  id, ticket_id,
                          notes                   author_id, update_type,
                                                  notes, created_at

  CompletionReport        Final repair report     id, ticket_id,
                                                  technician_id,
                                                  diagnosis, work_done,
                                                  completed_at

  Attachment              Related uploaded files  id, ticket_id,
                                                  uploaded_by_id,
                                                  file_path, created_at

  StatusHistory           Ticket status audit     id, ticket_id,
                          trail                   old_status, new_status,
                                                  changed_by_id,
                                                  changed_at, reason
  -----------------------------------------------------------------------

### Relationship summary

-   One customer can own many devices.
-   One customer can create many service tickets.
-   One device can have many service tickets over time.
-   One service ticket can have multiple assignments over time.
-   One technician can be assigned many tickets.
-   One service ticket can have many repair updates.
-   One service ticket can have one or more attachments.
-   One service ticket can have a status history.
-   A completed ticket should have the required completion report.

### Database design rules

-   Use primary keys and foreign keys.
-   Add unique constraints to ticket numbers.
-   Add indexes to common lookup fields where justified.
-   Define deletion behaviour deliberately (`PROTECT`, `SET_NULL` or
    carefully chosen alternatives).
-   Prefer archival/deactivation for records with service history.
-   Use Django ORM for normal database operations.
-   Use transactions for operations that must succeed or fail together.
-   Do not store passwords directly; use Django authentication.
-   Keep timestamps consistent and configure the application timezone.

### Multi-business support decision

A single-shop MVP can begin without complex multi-tenant infrastructure.
If the product is intended to serve multiple independent businesses,
decide early whether each business will be an organisation/tenant. In
that case, tenant ownership must be included in relevant records and
enforced in every query, API and permission check. Never rely on
frontend filtering for tenant isolation.

------------------------------------------------------------------------

## 12. UI / Page Inventory

Proposed pages:

  Page                   Main purpose
  ---------------------- -------------------------------------
  Login                  Secure user sign-in
  Dashboard              Operational overview
  Customer list          Search and manage customers
  Add/Edit customer      Customer form
  Customer details       Contact details and repair history
  Device list            Search registered devices
  Add/Edit device        Device registration form
  Ticket list            Search and filter repair tickets
  Create ticket          Register a new service request
  Ticket details         Full ticket timeline and assignment
  Technician list        Manage technicians
  Technician workspace   Assigned jobs and repair updates
  Completion report      Submit final repair details
  Reports                Operational summaries
  Profile / Settings     User profile and account settings

The customer portal is optional for the first MVP and should be
confirmed before implementation.

------------------------------------------------------------------------

## 13. Security and Privacy Guidelines

-   Use Django's built-in authentication and password hashing.
-   Keep CSRF protection enabled for session-authenticated forms.
-   Validate all user input on the server.
-   Use Django ORM or parameterised queries; do not build SQL by
    concatenating user input.
-   Enforce role permissions on every protected view and API endpoint.
-   Check object-level permissions before displaying or modifying a
    customer, device or ticket.
-   Prevent insecure direct object reference vulnerabilities by checking
    ownership/authorisation for every requested object.
-   Keep `SECRET_KEY`, database passwords, email credentials and API
    keys in environment variables.
-   Do not commit `.env`, database dumps, private uploads or production
    secrets.
-   Use HTTPS in production.
-   Restrict file upload types and sizes; do not trust filenames or
    browser-supplied content types.
-   Avoid exposing stack traces or sensitive system details to end
    users.
-   Log important administrative and ticket-status actions without
    logging passwords or sensitive secrets.
-   Collect only customer information needed for service operations.
-   Define retention and deletion practices appropriate to the business.

### Multi-tenant security (only if multi-business mode is selected)

-   Every tenant-owned record must be linked to an organisation.
-   Derive organisation access from the authenticated membership, not a
    freely editable form field.
-   Scope list, detail, update, delete and API queries by the active
    organisation.
-   Test that a user from Organisation A cannot access Organisation B's
    records by changing IDs or API parameters.
-   Add automated tests for cross-tenant access attempts before
    deployment.

------------------------------------------------------------------------

## 14. Validation and Business Rules

Examples of rules to implement and test:

1.  A ticket must reference a valid customer.
2.  A device selected for a ticket must belong to that customer, unless
    an authorised exception is defined.
3.  Ticket numbers must be unique.
4.  An inactive technician cannot receive a new assignment.
5.  A technician can update only tickets assigned to them, unless a
    supervisor permission applies.
6.  A completed ticket must contain the required completion information.
7.  A closed/delivered ticket cannot be casually edited; corrections
    should be controlled and auditable.
8.  Cancellation and on-hold actions should capture a reason where
    appropriate.
9.  Status changes must be recorded with user and timestamp.
10. Required fields and formats must be validated on the server.

------------------------------------------------------------------------

## 15. Local Development Setup

The commands below are a setup template. Confirm the installed Python
version and chosen Django version before pinning dependencies.

### Prerequisites

-   Python installed.
-   MySQL Server installed and running.
-   Git installed.
-   Code editor such as VS Code.
-   A terminal/command prompt.

### 15.1 Clone the repository

``` bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd RepairDesk
```

### 15.2 Create and activate a virtual environment

Windows PowerShell:

``` powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Windows Command Prompt:

``` cmd
python -m venv venv
venv\Scripts\activate
```

macOS / Linux:

``` bash
python3 -m venv venv
source venv/bin/activate
```

### 15.3 Install dependencies

After creating `requirements.txt`:

``` bash
pip install -r requirements.txt
```

### 15.4 Configure environment variables

Create a local `.env` file based on `.env.example`. Example variable
names:

``` env
DEBUG=True
SECRET_KEY=replace-with-a-local-development-secret
ALLOWED_HOSTS=127.0.0.1,localhost

DB_NAME=repairdesk_db
DB_USER=your_mysql_username
DB_PASSWORD=your_mysql_password
DB_HOST=127.0.0.1
DB_PORT=3306
```

Do not use these example values as production credentials. Ensure `.env`
is listed in `.gitignore`.

### 15.5 Create the database

Create a MySQL database using MySQL Workbench or the MySQL command line.
Example:

``` sql
CREATE DATABASE repairdesk_db
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

Configure Django to read the database settings from environment
variables.

### 15.6 Apply migrations

``` bash
python manage.py makemigrations
python manage.py migrate
```

### 15.7 Create an administrator account

``` bash
python manage.py createsuperuser
```

### 15.8 Run the development server

``` bash
python manage.py runserver
```

Open:

-   Application: `http://127.0.0.1:8000/`
-   Django Admin: `http://127.0.0.1:8000/admin/`

The URLs above are local development addresses, not production links.

------------------------------------------------------------------------

## 16. Testing Strategy

Use Django's test framework. Test both successful actions and
failure/permission cases.

### Minimum test checklist

  -----------------------------------------------------------------------
  Area                                Test cases
  ----------------------------------- -----------------------------------
  Authentication                      Valid login, invalid login, logout,
                                      protected page access

  Forms                               Required fields, invalid
                                      phone/email, invalid values

  Customers                           Create, view, update, archive

  Devices                             Create, view, update,
                                      customer-device relationship

  Tickets                             Unique ticket number, create, view,
                                      update, filter

  Assignment                          Assign active technician, reject
                                      inactive technician

  Permissions                         Technician cannot access admin-only
                                      actions

  Repair updates                      Add diagnosis and progress notes

  Status flow                         Valid transitions accepted; invalid
                                      transitions rejected

  Completion                          Required completion fields enforced

  History                             Previous tickets remain visible

  Database                            Data persists after server restart

  UI                                  Navigation and links work

  Responsive layout                   Desktop, tablet and mobile widths

  Security                            CSRF, object-level access, upload
                                      validation

  Tenant isolation                    Cross-organisation access blocked
                                      if multi-tenant mode is implemented
  -----------------------------------------------------------------------

Do not treat a page loading successfully as proof that its business
logic is correct.

------------------------------------------------------------------------

## 17. Git and GitHub Workflow

1.  Create a separate GitHub repository for RepairDesk.
2.  Commit the project structure early.
3.  Make small, meaningful commits.
4.  Do not commit secrets, virtual environments, cache files or private
    uploads.
5.  Push regularly; do not wait until the end.
6.  Use branches for larger features if helpful.

Example:

``` bash
git init
git add .
git commit -m "Initial Django project structure"
git branch -M main
git remote add origin <YOUR_GITHUB_REPOSITORY_URL>
git push -u origin main
```

Example commit messages:

-   `Create Django project and initial apps`
-   `Configure MySQL database connection`
-   `Add customer registration and management`
-   `Implement service ticket creation`
-   `Add technician assignment workflow`
-   `Add repair status history`
-   `Add dashboard summary cards`
-   `Add validation and permission tests`

------------------------------------------------------------------------

## 18. Development Roadmap

A suggested sequence for one developer. Adjust timing based on actual
progress and trainer deadlines.

  -----------------------------------------------------------------------
  Phase                   Work                    Completion evidence
  ----------------------- ----------------------- -----------------------
  1\. Planning            Confirm target          Approved PRD and
                          business, requirements, flowchart
                          workflow and scope      

  2\. Design              ER diagram, models,     Reviewed database
                          page sketches           design

  3\. Foundation          Django setup, MySQL,    App runs and migrations
                          GitHub, base layout     work

  4\. Accounts            Login, roles and        Authentication tests
                          permissions             pass

  5\. Customers and       CRUD and relationships  Records can be managed
  devices                                         correctly

  6\. Tickets             Ticket creation, unique Full ticket workflow
                          number and search       starts

  7\. Technicians         Technician profiles and Jobs can be assigned
                          assignment              securely

  8\. Repair workflow     Diagnosis, notes,       Repair can be completed
                          statuses and completion end-to-end

  9\. Dashboard and       Summaries, filters and  Useful operational
  history                 service history         overview

  10\. Testing and polish Security, validation,   Test checklist passes
                          responsive UI and bug   
                          fixes                   

  11\. Delivery           Documentation,          Submission package
                          screenshots, PPT and    ready
                          demo                    
  -----------------------------------------------------------------------

### Definition of MVP completion

The MVP is ready for a controlled demonstration when an administrator
can register a customer and device, create a ticket, assign a
technician, the technician can record diagnosis and repair progress, and
the administrator can verify completion and view the service history.
Access restrictions, validation and database persistence must also pass
tests.

------------------------------------------------------------------------

## 19. Risks and Mitigation

  -----------------------------------------------------------------------
  Risk                                Mitigation
  ----------------------------------- -----------------------------------
  Too many features                   Freeze MVP scope and defer
                                      enhancements

  Unclear repair-business workflow    Interview repair staff and observe
                                      real intake/repair steps

  Incorrect database relationships    Review ERD before building
                                      dependent modules

  Permission gaps                     Add role and object-level access
                                      tests

  Lost repair history                 Use archival and deliberate
                                      deletion rules

  Duplicate ticket numbers            Use database uniqueness and
                                      collision-safe generation

  Unreliable notifications            Make in-app status/history the
                                      source of truth

  Overcomplicated APIs                Start with Django templates; add
                                      DRF where required

  Unverified assumptions              Label assumptions and validate them
                                      with pilot users
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 20. Real-User Validation Plan

Before committing to specialised workflows, speak with at least two or
three people who work in the chosen repair-business segment.

Ask them:

1.  How do you currently register a customer and the item received?
2.  What information do you record at intake?
3.  How do you identify and find a repair job?
4.  How are jobs assigned to technicians?
5.  Which repair statuses do you actually use?
6.  How do you record diagnosis, parts and work performed?
7.  How do customers receive updates?
8.  How do you decide that an item is ready for delivery?
9.  What information do you need from previous repair history?
10. Which part of the current process causes the most confusion or
    repeated work?

Do not collect confidential customer records during interviews. Use
anonymised examples and obtain permission before observing a business
process.

Record findings, separate repeated problems from one-off preferences,
and update the PRD accordingly.

------------------------------------------------------------------------

## 21. Project Documentation and Submission Checklist

The project development guidelines require the following planning and
submission materials.

### Planning documentation

-   [ ] Project title and introduction.
-   [ ] Problem statement.
-   [ ] Project objectives.
-   [ ] Project scope and functional requirements.
-   [ ] Software and hardware requirements.
-   [ ] Technology stack.
-   [ ] Database design.
-   [ ] ER diagram.
-   [ ] Application flowchart/workflow.

### Development requirements

-   [ ] Registration, login and logout.
-   [ ] Suitable dashboard.
-   [ ] CRUD operations.
-   [ ] Database connectivity and data handling.
-   [ ] Responsive frontend.
-   [ ] Django models, views and URL routing.
-   [ ] Forms and validation.
-   [ ] CSRF protection and access control.
-   [ ] Django Admin integration where appropriate.
-   [ ] Error handling and user feedback.

### Coding and version control

-   [ ] Meaningful names.
-   [ ] Standard Django project/app structure.
-   [ ] Organised templates, CSS and JavaScript.
-   [ ] Business logic separated into suitable modules.
-   [ ] Django ORM used for normal database operations.
-   [ ] Helpful comments and reusable code.
-   [ ] Separate GitHub repository.
-   [ ] Regular commits with meaningful messages.
-   [ ] README setup instructions maintained.

### Testing

-   [ ] Registration, login and logout.
-   [ ] Invalid input and form validation.
-   [ ] Create, view, update and delete.
-   [ ] Database persistence.
-   [ ] Navigation and links.
-   [ ] Responsive layout.
-   [ ] Error handling and access restrictions.

### Final submission

-   [ ] Complete Django source code.
-   [ ] Project documentation in PDF.
-   [ ] Database design / ER diagram.
-   [ ] Screenshots of important pages.
-   [ ] GitHub repository link.
-   [ ] README.md with setup instructions.
-   [ ] Project presentation (PPT).
-   [ ] Working project demonstration.

### Presentation readiness

Be prepared to explain:

-   Project introduction, objectives and problem.
-   Technologies used and why selected.
-   Django project and app structure.
-   Database models and relationships.
-   How URLs, views and templates work together.
-   CRUD operations and important features.
-   A live working demonstration.
-   Challenges encountered and how they were resolved.

------------------------------------------------------------------------

## 22. Hardware and Software Requirements

### Suggested development hardware

-   Laptop or desktop capable of running Python, Django and MySQL.
-   Stable internet connection for package installation and GitHub.
-   Sufficient storage for source code, database and project
    documentation.

Exact minimum CPU, RAM and storage specifications should be recorded
based on the actual development machine and deployment target rather
than invented.

### Software

-   Supported Python release.
-   Django and compatible Django REST Framework release, if used.
-   MySQL Server.
-   MySQL Workbench or equivalent database client.
-   VS Code or another code editor.
-   Git.
-   Modern web browser.
-   Postman or equivalent API client, if APIs are implemented.

Pin tested package versions in `requirements.txt` before submission.

------------------------------------------------------------------------

## 23. Project Configuration and Deployment Notes

Development and production settings must be separated.

Before production deployment:

-   Set `DEBUG=False`.
-   Configure production `SECRET_KEY` through environment variables.
-   Set `ALLOWED_HOSTS` correctly.
-   Configure HTTPS and secure cookies.
-   Configure static and media file handling.
-   Use a managed or properly secured MySQL database.
-   Run migrations as part of a controlled deployment.
-   Back up the database.
-   Configure logging and error monitoring.
-   Do not expose Django Admin unnecessarily.
-   Test permissions using non-admin accounts.
-   Never publish database credentials or private customer data.

Deployment provider and hosting architecture are **not yet selected**.

------------------------------------------------------------------------

## 24. Decisions Still to Confirm

The following are open product decisions, not settled facts:

-   [ ] First target segment: computer/laptop repair, mobile repair,
    appliance repair or another service category.
-   [ ] Single repair business first, or multi-business SaaS from the
    beginning.
-   [ ] Whether customers get accounts in the first MVP.
-   [ ] Whether estimates and customer approval are required.
-   [ ] Whether spare-parts inventory belongs in the first release.
-   [ ] Whether invoices and payments are in scope.
-   [ ] Whether technicians use a responsive web interface or a PWA in
    the first release.
-   [ ] Whether Django templates alone are sufficient initially or DRF
    APIs are needed immediately.
-   [ ] Hosting and deployment provider.
-   [ ] Final ticket statuses and approval rules.

Resolve these decisions through a short PRD review and real-user
interviews before building features that depend on them.

------------------------------------------------------------------------

## 25. Project Principles

1.  Build the smallest complete repair workflow first.
2.  Prioritise correctness, security and usability over feature count.
3.  Do not add a feature without a user problem it solves.
4.  Keep customer and repair history accurate.
5.  Validate permissions on the backend.
6.  Test each module before moving to the next.
7.  Commit working progress regularly.
8.  Understand every part of the submitted code.
9.  Record assumptions and update this README when decisions change.
10. Demonstrate a complete working flow, not just disconnected screens.

------------------------------------------------------------------------

## 26. Current Project Status

This README is the **initial planning and specification baseline**. It
does not claim that the application, database, APIs or screens have
already been implemented.

  Area                       Status
  -------------------------- --------------------
  Project concept and name   Defined
  Brief description          Drafted
  General repair workflow    Proposed
  Initial modules            Proposed
  Technology stack           Proposed
  Target customer segment    Needs confirmation
  Functional requirements    Initial draft
  ER diagram                 Pending
  Django project setup       Not confirmed
  MySQL configuration        Not confirmed
  Implementation             Not confirmed
  Testing                    Pending
  Deployment                 Not selected

Update this section as work is completed. Only mark a feature complete
after it has been implemented and tested.

------------------------------------------------------------------------

## 27. Licence and Project Ownership

Add a licence only after deciding how the source code may be used and
distributed. If this is an individual academic or prototype project, do
not imply commercial rights, customer endorsements or production
readiness that have not been established.

------------------------------------------------------------------------

## 28. Contact and Repository

-   **Project:** RepairDesk -- Service & Repair Management Platform
-   **Developer:** \[Your Name\]
-   **Institution / Organisation:** \[Add if required\]
-   **GitHub Repository:** \[Add repository URL\]
-   **Project Demo:** \[Add demo URL when deployed\]

------------------------------------------------------------------------

*End of RepairDesk project specification.*
