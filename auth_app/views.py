from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.utils import timezone
from EmployeeManagement_app.models import Employee, Department, JobRole
from django.contrib import messages


def login_view(request):
    if request.method == 'POST':
        # Admin login
        if 'admin_username' in request.POST:
            username = request.POST['admin_username']
            password = request.POST['admin_password']
            user = authenticate(request, username=username, password=password)

            if user is not None and user.is_staff:
                auth_login(request, user)
                return redirect('/admin/')
            else:
                messages.error(request, 'Invalid admin credentials or not an admin.')
                return render(request, 'auth_app/login.html')

        # Employee login
        else:
            username = request.POST['username']
            password = request.POST['password']
            user = authenticate(request, username=username, password=password)

            if user is not None:
                auth_login(request, user)
                try:
                    employee = Employee.objects.get(user=user)
                    return redirect('employee-dashboard', employee_id=employee.employee_id)
                except Employee.DoesNotExist:
                    messages.error(request, 'Employee profile not found.')
                    return render(request, 'auth_app/login.html')
            else:
                messages.error(request, 'Invalid employee credentials.')
                return render(request, 'auth_app/login.html')

    return render(request, 'auth_app/login.html')



def logout_view(request):
    auth_logout(request)
    return redirect('authapp-login')



def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        date_of_birth = request.POST.get('date_of_birth')
        gender = request.POST.get('gender')
        phone_number = request.POST.get('phone_number')
        address = request.POST.get('address')
        department_id = request.POST.get('department')
        job_role_id = request.POST.get('job_role')

        # Validate password match
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            departments = Department.objects.all()
            job_roles = JobRole.objects.all()
            return render(request, 'auth_app/register.html', {
                'departments': departments,
                'job_roles': job_roles
            })

        # Check if username exists
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            departments = Department.objects.all()
            job_roles = JobRole.objects.all()
            return render(request, 'auth_app/register.html', {
                'departments': departments,
                'job_roles': job_roles
            })

        # Create Django user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        # Create employee profile
        Employee.objects.create(
            user=user,
            date_of_birth=date_of_birth,
            gender=gender,
            phone_number=phone_number,
            address=address,
            department_id=department_id,
            job_role_id=job_role_id,
            date_joined=timezone.now().date(),
            is_active=True
        )

        messages.success(request, "Registration successful. You can now log in.")
        return redirect('authapp-login')

    departments = Department.objects.all()
    job_roles = JobRole.objects.all()
    return render(request, 'auth_app/register.html', {
        'departments': departments,
        'job_roles': job_roles
    })



