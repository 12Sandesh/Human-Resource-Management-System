from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.http import JsonResponse
from .models import Employee, Attendance, Leave, Payroll
from datetime import datetime, timedelta
import calendar
import csv
from django.http import HttpResponse


def employee_dashboard(request, employee_id):
    try:
        employee = Employee.objects.get(employee_id=employee_id)
        
        # Security check: ensure user can only access their own dashboard
        if request.user.is_authenticated and hasattr(request.user, 'employee'):
            if request.user.employee.employee_id != employee_id:
                messages.error(request, 'Access denied.')
                return redirect('authapp-login')
        else:
            messages.error(request, 'Please log in.')
            return redirect('authapp-login')
        
        # Get current date and month information
        today = timezone.now().date()
        current_month_start = today.replace(day=1)
        
        # Calculate attendance statistics for current month
        monthly_attendance = Attendance.objects.filter(
            employee=employee,
            date__gte=current_month_start,
            date__lte=today
        )
        
        present_days = monthly_attendance.filter(status='Present').count()
        absent_days = monthly_attendance.filter(status='Absent').count()
        leave_days = monthly_attendance.filter(status='Leave').count()
        
        # Calculate total working days in current month (excluding weekends)
        total_working_days = 0
        current_date = current_month_start
        while current_date <= today:
            if current_date.weekday() < 5: 
                total_working_days += 1
            current_date += timedelta(days=1)
        
        # Calculate attendance rate
        attendance_rate = round((present_days / total_working_days) * 100, 1) if total_working_days > 0 else 0
        
        # Get leave statistics
        LEAVE_ALLOCATIONS = {
            'Sick': 10,
            'Casual': 5,
            'Annual': 15
        }
        
        # Calculate remaining leaves (only approved leaves count)
        approved_leaves = Leave.objects.filter(employee=employee, status='Approved')
        total_used_days = 0
        
        for leave in approved_leaves:
            # Calculate working days for each approved leave
            current_date = leave.start_date
            while current_date <= leave.end_date:
                if current_date.weekday() < 5:  # Monday=0 to Friday=4
                    total_used_days += 1
                current_date += timedelta(days=1)
        
        total_allocated = sum(LEAVE_ALLOCATIONS.values())
        remaining_leaves = max(0, total_allocated - total_used_days)
        
        # Get latest payroll information
        latest_payroll = Payroll.objects.filter(employee=employee).order_by('-payment_date').first()
        
        # Check if attendance is marked today
        attendance_marked_today = Attendance.objects.filter(
            employee=employee,
            date=today
        ).exists()
        
        # Get recent leave requests (last 5)
        recent_leaves = Leave.objects.filter(employee=employee).order_by('-applied_at')[:3]
        
        # Calculate leave breakdown by type
        leave_breakdown = {}
        for leave_type, allocation in LEAVE_ALLOCATIONS.items():
            used = 0
            for leave in approved_leaves.filter(leave_type=leave_type):
                current_date = leave.start_date
                while current_date <= leave.end_date:
                    if current_date.weekday() < 5:
                        used += 1
                    current_date += timedelta(days=1)
            leave_breakdown[leave_type] = {
                'used': used,
                'remaining': max(0, allocation - used)
            }
        
        # Get pending leave requests count
        pending_leaves_count = Leave.objects.filter(employee=employee, status='Pending').count()
        
        # Calculate YTD earnings
        current_year = today.year
        ytd_payrolls = Payroll.objects.filter(
            employee=employee,
            payment_date__year=current_year
        )
        ytd_earnings = sum(payroll.net_salary for payroll in ytd_payrolls)
        
        # Get recent notifications (simulated data - you can create a Notification model later)
        notifications = []
        
        # Add leave-related notifications
        if recent_leaves:
            latest_leave = recent_leaves[0]
            if latest_leave.status == 'Approved':
                notifications.append({
                    'icon': 'bi-check-circle-fill text-success',
                    'title': 'Leave Request Approved',
                    'message': f'Your {latest_leave.leave_type.lower()} leave request was approved.',
                    'time': latest_leave.applied_at
                })
            elif latest_leave.status == 'Rejected':
                notifications.append({
                    'icon': 'bi-x-circle-fill text-danger',
                    'title': 'Leave Request Rejected',
                    'message': f'Your {latest_leave.leave_type.lower()} leave request was rejected.',
                    'time': latest_leave.applied_at
                })
        
        # Add payroll notification if latest payroll is recent (within last 7 days)
        if latest_payroll and (today - latest_payroll.payment_date).days <= 7:
            notifications.append({
                'icon': 'bi-cash-coin text-info',
                'title': 'Payroll Processed',
                'message': f'Your salary for {latest_payroll.payment_date.strftime("%B %Y")} has been processed.',
                'time': latest_payroll.created_at
            })
        
        # Add attendance reminder if not marked today
        if not attendance_marked_today and today.weekday() < 5:  # Only on weekdays
            notifications.append({
                'icon': 'bi-clock text-warning',
                'title': 'Attendance Reminder',
                'message': 'Don\'t forget to mark your attendance for today.',
                'time': timezone.now()
            })
        
        # Sort notifications by time (most recent first)
        notifications.sort(key=lambda x: x['time'], reverse=True)
        notifications = notifications[:3]  # Limit to 3 most recent
        
        # Calculate performance metrics
        # Tasks completed (you can create a Task model later, using attendance as placeholder)
        tasks_completed = present_days  # Placeholder
        
        # Performance score (based on attendance rate)
        performance_score = attendance_rate
        
        context = {
            'employee': employee,
            'today': today,
            'present_days': present_days,
            'absent_days': absent_days,
            'leave_days': leave_days,
            'total_working_days': total_working_days,
            'attendance_rate': attendance_rate,
            'remaining_leaves': remaining_leaves,
            'latest_payroll': latest_payroll,
            'attendance_marked_today': attendance_marked_today,
            'recent_leaves': recent_leaves,
            'leave_breakdown': leave_breakdown,
            'pending_leaves_count': pending_leaves_count,
            'ytd_earnings': ytd_earnings,
            'notifications': notifications,
            'tasks_completed': tasks_completed,
            'performance_score': performance_score,
            'total_allocated_leaves': total_allocated,
            'total_used_leaves': total_used_days,
        }
            
        return render(request, 'EmployeeManagement_app/dashboard.html', context)
    except Employee.DoesNotExist:
        messages.error(request, 'Employee not found.')
        return redirect('authapp-login')


def get_attendance_data(employee, period='current'):
    """Helper function to get attendance data for different periods"""
    today = timezone.now().date()
    
    if period == 'current':
        start_date = today.replace(day=1)
        end_date = today
    elif period == 'last':
        # Get last month's first and last day
        if today.month == 1:
            last_month = 12
            year = today.year - 1
        else:
            last_month = today.month - 1
            year = today.year
        
        start_date = datetime(year, last_month, 1).date()
        end_date = datetime(year, last_month, calendar.monthrange(year, last_month)[1]).date()
    else:  # all time - FIXED
        # Get the earliest attendance record or employee join date
        earliest_attendance = Attendance.objects.filter(employee=employee).order_by('date').first()
        if earliest_attendance:
            start_date = earliest_attendance.date
        else:
            # Fallback to employee join date or 1 year ago
            if hasattr(employee, 'date_joined') and employee.date_joined:
                start_date = employee.date_joined
            else:
                start_date = today - timedelta(days=365)
        end_date = today
    
    # Get attendance records for the period
    attendance_records = Attendance.objects.filter(
        employee=employee,
        date__range=[start_date, end_date]
    ).order_by('-date')
    
    # Calculate statistics
    present_count = attendance_records.filter(status='Present').count()
    absent_count = attendance_records.filter(status='Absent').count()
    leave_count = attendance_records.filter(status='Leave').count()
    
    # Calculate total working days (excluding weekends)
    total_days = 0
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() < 5:  # Monday = 0, Friday = 4
            total_days += 1
        current_date += timedelta(days=1)
    
    # Calculate attendance rate
    if total_days > 0:
        attendance_rate = round((present_count / total_days) * 100, 1)
    else:
        attendance_rate = 0
    
    return {
        'attendance_records': attendance_records,
        'present_count': present_count,
        'absent_count': absent_count,
        'leave_count': leave_count,
        'total_working_days': total_days,
        'attendance_rate': attendance_rate,
        'period_label': get_period_label(period, start_date, end_date)
    }


def get_period_label(period, start_date, end_date):
    """Get human readable period label"""
    if period == 'current':
        return f"This Month ({start_date.strftime('%B %Y')})"
    elif period == 'last':
        return f"Last Month ({start_date.strftime('%B %Y')})"
    else:
        return f"All Time ({start_date.strftime('%b %Y')} - {end_date.strftime('%b %Y')})"


def attendance(request, employee_id):
    if not request.user.is_authenticated:
        return redirect('authapp-login')
    
    try:
        employee = Employee.objects.get(employee_id=employee_id)
        
        # Security check: ensure user can only access their own data
        if request.user.employee.employee_id != employee_id:
            messages.error(request, 'Access denied.')
            return redirect('authapp-login')
            
    except Employee.DoesNotExist:
        messages.error(request, "Employee not found.")
        return redirect('authapp-login')
    
    # Handle AJAX requests for period changes
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        period = request.GET.get('period', 'current')
        data = get_attendance_data(employee, period)
        
        # Convert attendance records to JSON serializable format
        records_data = []
        for record in data['attendance_records']:
            # Get the actual time when attendance was marked
            display_time = '--'
            if record.status == 'Present' and hasattr(record, 'marked_time') and record.marked_time:
                display_time = record.marked_time.strftime('%I:%M %p')
            elif record.status == 'Present':
                display_time = '09:00 AM'  # Default fallback
                
            records_data.append({
                'date': record.date.strftime('%Y-%m-%d'),
                'date_formatted': record.date.strftime('%b %d, %Y'),
                'day': record.date.strftime('%A'),
                'status': record.status,
                'time': display_time
            })
        
        return JsonResponse({
            'records': records_data,
            'present_count': data['present_count'],
            'absent_count': data['absent_count'],
            'leave_count': data['leave_count'],
            'total_working_days': data['total_working_days'],
            'attendance_rate': data['attendance_rate'],
            'period_label': data['period_label']
        })
    
    # Handle attendance marking
    if request.method == 'POST':
        today = timezone.now().date()
        current_time = timezone.now().time()
        
        # Check if attendance already marked today
        existing_attendance = Attendance.objects.filter(
            employee=employee,
            date=today
        ).first()
        
        if existing_attendance:
            messages.warning(request, "Attendance already marked for today.")
        else:
            # Mark attendance with current time
            attendance_record = Attendance.objects.create(
                employee=employee,
                date=today,
                status='Present'
            )
            # Store the actual time when attendance was marked
            attendance_record.marked_time = current_time
            attendance_record.save()
            
            messages.success(request, "Attendance marked successfully!")
            return redirect('employee-attendance', employee_id=employee_id)  # FIXED URL NAME
    
    # Get current month data by default
    attendance_data = get_attendance_data(employee, 'current')
    
    # Check if attendance marked today
    today = timezone.now().date()
    attendance_marked_today = Attendance.objects.filter(
        employee=employee,
        date=today
    ).exists()
    
    context = {
        'employee': employee,
        'attendance_records': attendance_data['attendance_records'],
        'present_count': attendance_data['present_count'],
        'absent_count': attendance_data['absent_count'],
        'leave_count': attendance_data['leave_count'],
        'total_working_days': attendance_data['total_working_days'],
        'attendance_rate': attendance_data['attendance_rate'],
        'attendance_marked_today': attendance_marked_today,
        'period_label': attendance_data['period_label']
    }
    
    return render(request, 'EmployeeManagement_app/attendance.html', context)


def leave(request, employee_id):
    if not request.user.is_authenticated:
        return redirect('authapp-login')
    
    try:
        employee = Employee.objects.get(employee_id=employee_id)
        
        # Security check: ensure user can only access their own data
        if request.user.employee.employee_id != employee_id:
            messages.error(request, 'Access denied.')
            return redirect('authapp-login')
            
    except Employee.DoesNotExist:
        messages.error(request, "Employee not found.")
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
                    # Create leave record (status will default to 'Pending')
                    leave_record = Leave.objects.create(
                        employee=employee,
                        leave_type=leave_type,
                        start_date=start_date,
                        end_date=end_date,
                        reason=reason
                        # No need to set status - it defaults to 'Pending'
                    )
                    
                    # Do NOT create attendance records until leave is approved
                    # Only create them when admin approves the leave
                    
                    messages.success(request, "Leave application submitted successfully! Waiting for approval.")
                else:
                    messages.error(request, "End date must be after start date.")
            except ValueError:
                messages.error(request, "Invalid date format.")
        else:
            messages.error(request, "All fields are required.")
    
    # Get leave records and calculate duration for each
    leave_records = Leave.objects.filter(
        employee=employee
    ).order_by('-applied_at')
    
    # Add duration calculation to each leave record (working days only)
    for leave in leave_records:
        # Calculate working days between start and end date
        current_date = leave.start_date
        working_days = 0
        while current_date <= leave.end_date:
            if current_date.weekday() < 5:  # Monday=0 to Friday=4 (exclude weekends)
                working_days += 1
            current_date += timedelta(days=1)
        leave.duration = working_days
    
    # Define leave allocations per type (you can make this configurable)
    LEAVE_ALLOCATIONS = {
        'Sick': 10,
        'Casual': 5,
        'Annual': 15
    }
    
    # Calculate used leaves by type (only approved leaves)
    approved_leaves = leave_records.filter(status='Approved')
    
    leave_usage = {}
    total_used = 0
    total_allocated = sum(LEAVE_ALLOCATIONS.values())
    
    for leave_type, allocation in LEAVE_ALLOCATIONS.items():
        # Sum duration for each leave type (only count working days)
        used = 0
        for leave in approved_leaves.filter(leave_type=leave_type):
            # Calculate working days between start and end date
            current_date = leave.start_date
            days_count = 0
            while current_date <= leave.end_date:
                if current_date.weekday() < 5:  # Monday=0 to Friday=4
                    days_count += 1
                current_date += timedelta(days=1)
            used += days_count
        
        remaining = max(0, allocation - used)  # Ensure it doesn't go negative
        leave_usage[leave_type] = {
            'used': used,
            'allocated': allocation,
            'remaining': remaining
        }
        total_used += used
    
    total_remaining = max(0, total_allocated - total_used)  # Ensure it doesn't go negative
    
    context = {
        'employee': employee,
        'leave_records': leave_records,
        'leave_usage': leave_usage,
        'total_allocated': total_allocated,
        'total_used': total_used,
        'remaining_leaves': total_remaining,
    }
    
    return render(request, 'EmployeeManagement_app/leave.html', context)


def payroll(request, employee_id):
    if not request.user.is_authenticated:
        return redirect('authapp-login')
    
    try:
        employee = Employee.objects.get(employee_id=employee_id)
        
        # Security check: ensure user can only access their own data
        if request.user.employee.employee_id != employee_id:
            messages.error(request, 'Access denied.')
            return redirect('authapp-login')
            
    except Employee.DoesNotExist:
        messages.error(request, "Employee not found.")
        return redirect('authapp-login')
    
    # Get payroll records
    payroll_records = Payroll.objects.filter(
        employee=employee
    ).order_by('-payment_date')
    
    # Calculate summary statistics
    payroll_summary = {}
    if payroll_records:
        latest_payroll = payroll_records.first()
        
        # Calculate yearly totals
        total_records = payroll_records.count()
        total_basic_salary = sum(record.basic_salary for record in payroll_records)
        total_allowances = sum(record.allowances for record in payroll_records)
        total_deductions = sum(record.deductions for record in payroll_records)
        total_net_salary = sum(record.net_salary for record in payroll_records)
        
        # Calculate projections
        projected_annual_salary = latest_payroll.net_salary * 12
        ytd_earnings = total_net_salary
        
        # NEW: Calculate total earnings for YTD display
        total_ytd_earnings = total_net_salary
        
        # NEW: Calculate average monthly salary
        average_monthly_salary = total_net_salary / total_records if total_records > 0 else 0
        
        payroll_summary = {
            'latest_payroll': latest_payroll,
            'total_records': total_records,
            'total_basic_salary': total_basic_salary,
            'total_allowances': total_allowances,
            'total_deductions': total_deductions,
            'total_net_salary': total_net_salary,
            'projected_annual_salary': projected_annual_salary,
            'ytd_earnings': ytd_earnings,
            'total_ytd_earnings': total_ytd_earnings,  # NEW
            'average_monthly_salary': average_monthly_salary,  # UPDATED
            'total_tax_deducted': total_deductions,  # NEW: for tax display
        }
    
    context = {
        'employee': employee,
        'payroll_records': payroll_records,
        'payroll_summary': payroll_summary,
    }
    
    return render(request, 'EmployeeManagement_app/payroll.html', context)


def export_payroll_report(request, employee_id):
    """Export payroll report as CSV"""
    if not request.user.is_authenticated:
        return redirect('authapp-login')
    
    try:
        employee = Employee.objects.get(employee_id=employee_id)
        
        # Security check: ensure user can only access their own data
        if request.user.employee.employee_id != employee_id:
            messages.error(request, 'Access denied.')
            return redirect('authapp-login')
            
    except Employee.DoesNotExist:
        messages.error(request, "Employee not found.")
        return redirect('authapp-login')
    
    # Get payroll records
    payroll_records = Payroll.objects.filter(
        employee=employee
    ).order_by('-payment_date')
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    filename = f"Payroll_Report_{employee.employee_id}_{timezone.now().strftime('%Y_%m_%d')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Create CSV writer
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'Employee ID',
        'Employee Name',
        'Payment Period',
        'Payment Date',
        'Basic Salary',
        'Allowances',
        'Deductions',
        'Net Salary',
        'Processed On',
        'Generated On'
    ])
    
    # Write payroll records
    for payroll in payroll_records:
        writer.writerow([
            employee.employee_id,
            employee.full_name,
            payroll.payment_date.strftime('%B %Y'),
            payroll.payment_date.strftime('%Y-%m-%d'),
            f"${payroll.basic_salary:.2f}",
            f"${payroll.allowances:.2f}",
            f"${payroll.deductions:.2f}",
            f"${payroll.net_salary:.2f}",
            payroll.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    # Write summary statistics
    writer.writerow([])  # Empty row
    writer.writerow(['PAYROLL SUMMARY'])
    
    if payroll_records:
        # Calculate total statistics
        total_records = payroll_records.count()
        total_basic_salary = sum([record.basic_salary for record in payroll_records])
        total_allowances = sum([record.allowances for record in payroll_records])
        total_deductions = sum([record.deductions for record in payroll_records])
        total_net_salary = sum([record.net_salary for record in payroll_records])
        
        # Get latest and earliest payroll dates
        latest_payroll = payroll_records.first()
        earliest_payroll = payroll_records.last()
        
        writer.writerow(['Total Payroll Records', total_records])
        writer.writerow(['Latest Payment', latest_payroll.payment_date.strftime('%Y-%m-%d')])
        writer.writerow(['Earliest Payment', earliest_payroll.payment_date.strftime('%Y-%m-%d')])
        writer.writerow(['Total Basic Salary Paid', f"${total_basic_salary:.2f}"])
        writer.writerow(['Total Allowances Paid', f"${total_allowances:.2f}"])
        writer.writerow(['Total Deductions', f"${total_deductions:.2f}"])
        writer.writerow(['Total Net Salary Paid', f"${total_net_salary:.2f}"])
        
        # Average calculations
        avg_basic = total_basic_salary / total_records
        avg_allowances = total_allowances / total_records
        avg_deductions = total_deductions / total_records
        avg_net = total_net_salary / total_records
        
        writer.writerow([])
        writer.writerow(['AVERAGE CALCULATIONS'])
        writer.writerow(['Average Basic Salary', f"${avg_basic:.2f}"])
        writer.writerow(['Average Allowances', f"${avg_allowances:.2f}"])
        writer.writerow(['Average Deductions', f"${avg_deductions:.2f}"])
        writer.writerow(['Average Net Salary', f"${avg_net:.2f}"])
    else:
        writer.writerow(['No payroll records found'])
    
    return response


def export_attendance_report(request, employee_id):
    """Export attendance report as CSV"""
    if not request.user.is_authenticated:
        return redirect('authapp-login')
    
    try:
        employee = Employee.objects.get(employee_id=employee_id)
        
        # Security check: ensure user can only access their own data
        if request.user.employee.employee_id != employee_id:
            messages.error(request, 'Access denied.')
            return redirect('authapp-login')
            
    except Employee.DoesNotExist:
        messages.error(request, "Employee not found.")
        return redirect('authapp-login')
    
    # Get the period from request (default to current month)
    period = request.GET.get('period', 'current')
    attendance_data = get_attendance_data(employee, period)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    
    # Generate filename with period info
    period_label = attendance_data['period_label'].replace(' ', '_').replace('(', '').replace(')', '')
    filename = f"Attendance_Report_{employee.employee_id}_{period_label}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Create CSV writer
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'Employee ID',
        'Employee Name',
        'Date',
        'Day',
        'Status',
        'Time Marked',
        'Report Period',
        'Generated On'
    ])
    
    # Write attendance records
    for record in attendance_data['attendance_records']:
        time_marked = '--'
        if record.status == 'Present' and hasattr(record, 'marked_time') and record.marked_time:
            time_marked = record.marked_time.strftime('%I:%M %p')
        elif record.status == 'Present':
            time_marked = '09:00 AM'
            
        writer.writerow([
            employee.employee_id,
            employee.full_name,
            record.date.strftime('%Y-%m-%d'),
            record.date.strftime('%A'),
            record.status,
            time_marked,
            attendance_data['period_label'],
            timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    # Write summary statistics
    writer.writerow([])  # Empty row
    writer.writerow(['SUMMARY STATISTICS'])
    writer.writerow(['Present Days', attendance_data['present_count']])
    writer.writerow(['Absent Days', attendance_data['absent_count']])
    writer.writerow(['Leave Days', attendance_data['leave_count']])
    writer.writerow(['Total Working Days', attendance_data['total_working_days']])
    writer.writerow(['Attendance Rate', f"{attendance_data['attendance_rate']}%"])
    
    return response


def export_leave_report(request, employee_id):
    """Export leave report as CSV"""
    if not request.user.is_authenticated:
        return redirect('authapp-login')
    
    try:
        employee = Employee.objects.get(employee_id=employee_id)
        
        # Security check: ensure user can only access their own data
        if request.user.employee.employee_id != employee_id:
            messages.error(request, 'Access denied.')
            return redirect('authapp-login')
            
    except Employee.DoesNotExist:
        messages.error(request, "Employee not found.")
        return redirect('authapp-login')
    
    # Get leave records
    leave_records = Leave.objects.filter(
        employee=employee
    ).order_by('-applied_at')
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    filename = f"Leave_Report_{employee.employee_id}_{timezone.now().strftime('%Y_%m_%d')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Create CSV writer
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'Employee ID',
        'Employee Name',
        'Leave Type',
        'Start Date',
        'End Date',
        'Duration (Days)',
        'Reason',
        'Status',
        'Applied On',
        'Generated On'
    ])
    
    # Write leave records
    for leave in leave_records:
        # Calculate working days duration
        current_date = leave.start_date
        working_days = 0
        while current_date <= leave.end_date:
            if current_date.weekday() < 5:  # Monday=0 to Friday=4
                working_days += 1
            current_date += timedelta(days=1)
        
        writer.writerow([
            employee.employee_id,
            employee.full_name,
            leave.get_leave_type_display(),
            leave.start_date.strftime('%Y-%m-%d'),
            leave.end_date.strftime('%Y-%m-%d'),
            working_days,
            leave.reason,
            leave.status,
            leave.applied_at.strftime('%Y-%m-%d %H:%M:%S'),
            timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    # Write summary statistics
    writer.writerow([])  # Empty row
    writer.writerow(['LEAVE SUMMARY'])
    
    # Calculate leave statistics
    total_leaves = leave_records.count()
    approved_leaves = leave_records.filter(status='Approved').count()
    pending_leaves = leave_records.filter(status='Pending').count()
    rejected_leaves = leave_records.filter(status='Rejected').count()
    
    # Calculate total approved leave days
    total_approved_days = 0
    for leave in leave_records.filter(status='Approved'):
        current_date = leave.start_date
        while current_date <= leave.end_date:
            if current_date.weekday() < 5:  # Monday=0 to Friday=4
                total_approved_days += 1
            current_date += timedelta(days=1)
    
    writer.writerow(['Total Applications', total_leaves])
    writer.writerow(['Approved Applications', approved_leaves])
    writer.writerow(['Pending Applications', pending_leaves])
    writer.writerow(['Rejected Applications', rejected_leaves])
    writer.writerow(['Total Approved Leave Days', total_approved_days])
    
    # Leave type breakdown
    writer.writerow([])
    writer.writerow(['LEAVE TYPE BREAKDOWN'])
    for leave_type in ['Sick', 'Casual', 'Annual']:
        type_count = leave_records.filter(leave_type=leave_type).count()
        approved_type_count = leave_records.filter(leave_type=leave_type, status='Approved').count()
        writer.writerow([f'{leave_type} Leave Applications', type_count])
        writer.writerow([f'{leave_type} Leave Approved', approved_type_count])
    
    return response