from django.db import models
from django.contrib.auth.models import User

# Employee Management Models
class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class JobRole(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="roles")

    def __str__(self):
        return f"{self.title} - {self.department.name}"


class Employee(models.Model):
    # Link to Django's User model for authentication
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    
    employee_id = models.CharField(
        max_length=10, unique=True, editable=False  # Changed from primary_key=True
    )
    
    # Personal Information
    date_of_birth = models.DateField(
        help_text="YYYY-MM-DD", verbose_name="Date of Birth"
    )
    gender_choices = [('M', 'Male'), ('F', 'Female'), ('O', 'Other')]
    gender = models.CharField(max_length=1, choices=gender_choices)
    phone_number = models.CharField(max_length=15)
    address = models.CharField(max_length=50)  

    # Work Information
    department = models.ForeignKey(
        'Department', on_delete=models.SET_NULL, null=True
    )
    job_role = models.ForeignKey(
        'JobRole', on_delete=models.SET_NULL, null=True
    )

    date_joined = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.employee_id:  
            last_employee = Employee.objects.all().order_by('employee_id').last()
            if last_employee:
                # Extract number part from last employee_id (e.g., EMP005 → 5)
                last_id = int(last_employee.employee_id.replace("EMP", ""))
                new_id = f"EMP{last_id + 1:03d}"  # EMP006
            else:
                new_id = "EMP001"
            self.employee_id = new_id
        super().save(*args, **kwargs)

    @property
    def first_name(self):
        return self.user.first_name
    
    @property
    def last_name(self):
        return self.user.last_name
    
    @property
    def email(self):
        return self.user.email
    
    @property
    def full_name(self):
        return f"{self.user.first_name} {self.user.last_name}"

    def __str__(self):
        return f"{self.employee_id} - {self.full_name}"


class Attendance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    date = models.DateField()
    status_choices = [('Present', 'Present'),
                      ('Absent', 'Absent'), ('Leave', 'Leave')]
    status = models.CharField(max_length=10, choices=status_choices)

    class Meta:
        unique_together = ('employee', 'date')  # Prevent duplicate entries

    def __str__(self):
        return f"{self.employee} - {self.date} - {self.status}"


class Leave(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    leave_type_choices = [
        ('Sick', 'Sick Leave'), ('Casual', 'Casual Leave'), ('Annual', 'Annual Leave')]
    leave_type = models.CharField(max_length=10, choices=leave_type_choices)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status_choices = [('Pending', 'Pending'), ('Approved', 'Approved'), ('Rejected', 'Rejected')]
    status = models.CharField(
        max_length=10, choices=status_choices, default='Pending')
    
    applied_at = models.DateTimeField(auto_now_add=True)  # Track when leave was applied

    def __str__(self):
        return f"{self.employee} - {self.leave_type} ({self.status})"


class Payroll(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    basic_salary = models.DecimalField(max_digits=10, decimal_places=2)
    allowances = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)
    deductions = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)
    net_salary = models.DecimalField(max_digits=10, decimal_places=2, editable=False)  # Auto-calculated
    payment_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.net_salary = self.basic_salary + self.allowances - self.deductions
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ('employee', 'payment_date')  # Prevent duplicate payroll entries

    def __str__(self):
        return f"{self.employee} - {self.payment_date}"