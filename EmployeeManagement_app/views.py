from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count
from .models import Employee, Attendance, Leave, Payroll
from datetime import datetime, timedelta


def employee_dashboard(request, employee_id):
    try:
        employee = Employee.objects.get(employee_id=employee_id)
        return render(request, 'EmployeeManagement_app/dashboard.html', {'employee': employee})
    except Employee.DoesNotExist:
        messages.error(request, 'Employee not found.')
        return redirect('authapp-login')
    



def attendance(request):
    if not request.user.is_authenticated:
        return redirect('authapp-login')
    
    try:
        employee = request.user.employee
    except Employee.DoesNotExist:
        messages.error(request, "Employee profile not found.")
        return redirect('authapp-login')
    
    # Handle attendance marking
    if request.method == 'POST':
        today = timezone.now().date()
        
        # Check if attendance already marked today
        existing_attendance = Attendance.objects.filter(
            employee=employee,
            date=today
        ).first()
        
        if existing_attendance:
            messages.warning(request, "Attendance already marked for today.")
        else:
            # Mark attendance
            Attendance.objects.create(
                employee=employee,
                date=today,
                status='Present'
            )
            messages.success(request, "Attendance marked successfully!")
    
    # Get attendance records for current month
    current_month = timezone.now().month
    current_year = timezone.now().year
    
    attendance_records = Attendance.objects.filter(
        employee=employee,
        date__month=current_month,
        date__year=current_year
    ).order_by('-date')
    
    # Check if attendance marked today
    today = timezone.now().date()
    attendance_marked_today = Attendance.objects.filter(
        employee=employee,
        date=today
    ).exists()
    
    context = {
        'employee': employee,
        'attendance_records': attendance_records,
        'attendance_marked_today': attendance_marked_today,
    }
    
    return render(request, 'EmployeeManagement_app/attendance.html', context)


def leave(request):
    if not request.user.is_authenticated:
        return redirect('authapp-login')
    
    try:
        employee = request.user.employee
    except Employee.DoesNotExist:
        messages.error(request, "Employee profile not found.")
        return redirect('authapp-login')
    
    # Handle leave application
    if request.method == 'POST':
        leave_type = request.POST.get('leave_type')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        reason = request.POST.get('reason')
        
        if leave_type and start_date and end_date and reason:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                
                if start_date <= end_date:
                    Leave.objects.create(
                        employee=employee,
                        leave_type=leave_type,
                        start_date=start_date,
                        end_date=end_date,
                        reason=reason
                    )
                    messages.success(request, "Leave application submitted successfully!")
                else:
                    messages.error(request, "End date must be after start date.")
            except ValueError:
                messages.error(request, "Invalid date format.")
        else:
            messages.error(request, "All fields are required.")
    
    # Get leave records
    leave_records = Leave.objects.filter(
        employee=employee
    ).order_by('-applied_at')
    
    context = {
        'employee': employee,
        'leave_records': leave_records,
    }
    
    return render(request, 'EmployeeManagement_app/leave.html', context)


def payroll(request):
    if not request.user.is_authenticated:
        return redirect('authapp-login')
    
    try:
        employee = request.user.employee
    except Employee.DoesNotExist:
        messages.error(request, "Employee profile not found.")
        return redirect('authapp-login')
    
    # Get payroll records
    payroll_records = Payroll.objects.filter(
        employee=employee
    ).order_by('-payment_date')
    
    context = {
        'employee': employee,
        'payroll_records': payroll_records,
    }
    
    return render(request, 'EmployeeManagement_app/payroll.html', context)