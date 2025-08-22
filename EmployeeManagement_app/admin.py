from django.contrib import admin
from EmployeeManagement_app.models import Department, JobRole, Employee, Attendance, Leave, Payroll

# Register your models here.
admin.site.register([Department, JobRole, Employee, Attendance, Leave, Payroll])
