import time
import logging
from flask import Blueprint, render_template_string, request, jsonify
from supabase import create_client, Client

guard_bp = Blueprint('guard_bp', __name__)

SUPABASE_URL = "https://qciehqzajzaejhsjzrdm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFjaWVocXphanphZWpoc2p6cmRtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODkwODQwNDksImV4cCI6MjEwNDY2MDA0OX0.0An1BSRjssOI7SliI1lC3jkMo14XVHbUnfXFt015Uyo"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

HTML_GUARD_STATION = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GuardGate | Admin Management</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #f2f7f3 0%, #eaf3ed 50%, #f4f8f5 100%);
        }
    </style>
    <script>
        let currentCollege = 'ALL';

        // Custom non-blocking toast notifications (Eliminates 'localhost says')
        function showToast(message, type = 'success', duration = 4000) {
            const container = document.getElementById('toast-container');
            if (!container) return;

            const toast = document.createElement('div');
            toast.className = 'pointer-events-auto flex items-start gap-3 p-4 rounded-xl shadow-lg border transition-all duration-300 transform translate-y-2 opacity-0 text-sm font-medium';
            
            let iconSvg = '';
            if (type === 'success') {
                toast.className += ' bg-emerald-50 text-emerald-900 border-emerald-200 shadow-emerald-900/5';
                iconSvg = `<svg class="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>`;
            } else if (type === 'error') {
                toast.className += ' bg-rose-50 text-rose-900 border-rose-200 shadow-rose-900/5';
                iconSvg = `<svg class="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>`;
            } else {
                toast.className += ' bg-slate-50 text-slate-900 border-slate-200';
                iconSvg = `<svg class="w-5 h-5 text-slate-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`;
            }

            toast.innerHTML = `
                ${iconSvg}
                <div class="flex-1 text-xs leading-relaxed break-words">${message}</div>
                <button onclick="this.parentElement.remove()" class="text-slate-400 hover:text-slate-600 p-0.5 rounded-lg transition-colors">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            `;

            container.appendChild(toast);
            requestAnimationFrame(() => {
                toast.classList.remove('translate-y-2', 'opacity-0');
                toast.classList.add('translate-y-0', 'opacity-100');
            });

            setTimeout(() => {
                toast.classList.add('opacity-0', 'translate-y-2');
                setTimeout(() => toast.remove(), 300);
            }, duration);
        }

        function filterCollege(code) {
            currentCollege = code;
            fetchStudents();
            fetchLogs();
        }

        function fetchStudents() {
            const query = document.getElementById('search-input').value;
            fetch(`/api/students?college=${currentCollege}&q=${encodeURIComponent(query)}`)
                .then(r => r.json())
                .then(data => {
                    const tbody = document.getElementById('students-tbody');
                    tbody.innerHTML = '';
                    if (data.length === 0) {
                        tbody.innerHTML = `<tr><td colspan="5" class="p-6 text-center text-slate-400 text-xs">No visitor records found.</td></tr>`;
                        return;
                    }
                    data.forEach(s => {
                        const safeId = (s.student_id || '').replace(/'/g, "\\'");
                        const safeName = (s.normalized_name || '').replace(/'/g, "\\'");
                        const safeCourse = (s.course_year || '').replace(/'/g, "\\'");
                        const safeCollege = (s.college || '').replace(/'/g, "\\'");

                        let tagClass = 'bg-emerald-50 text-emerald-800 border-emerald-200';
                        if (s.college === 'Parent') tagClass = 'bg-purple-50 text-purple-800 border-purple-200';
                        else if (s.college === 'Faculty') tagClass = 'bg-amber-50 text-amber-800 border-amber-200';
                        else if (s.college === 'Others') tagClass = 'bg-slate-100 text-slate-700 border-slate-200';

                        tbody.innerHTML += `
                            <tr class="border-b border-slate-100 text-xs text-slate-700 hover:bg-emerald-50/30 transition-colors">
                                <td class="p-3 font-semibold text-slate-900">${s.student_id}</td>
                                <td class="p-3 font-medium">${s.normalized_name}</td>
                                <td class="p-3"><span class="border text-[11px] px-2.5 py-0.5 rounded-full font-semibold ${tagClass}">${s.college}</span></td>
                                <td class="p-3 text-slate-600">${s.course_year || '-'}</td>
                                <td class="p-3 flex items-center gap-1.5">
                                    <button onclick="openEditModal('${safeId}', '${safeName}', '${safeCourse}', '${safeCollege}')" class="text-xs bg-emerald-50 text-emerald-800 border border-emerald-200/80 px-2.5 py-1 rounded-lg hover:bg-emerald-100 font-medium transition">Edit Info</button>
                                    <button onclick="manualTime('${safeId}', 'Time In')" class="text-xs bg-emerald-600 text-white px-2.5 py-1 rounded-lg hover:bg-emerald-700 font-medium transition shadow-xs">Time In</button>
                                    <button onclick="manualTime('${safeId}', 'Time Out')" class="text-xs bg-rose-50 text-rose-700 border border-rose-200 px-2.5 py-1 rounded-lg hover:bg-rose-100 font-medium transition">Time Out</button>
                                </td>
                            </tr>`;
                    });
                })
                .catch(() => {});
        }

        function fetchLogs() {
            fetch(`/api/logs?college=${currentCollege}`)
                .then(r => r.json())
                .then(data => {
                    const tbody = document.getElementById('logs-tbody');
                    tbody.innerHTML = '';
                    if (data.length === 0) {
                        tbody.innerHTML = `<tr><td colspan="4" class="p-6 text-center text-slate-400 text-xs">No time logs recorded yet.</td></tr>`;
                        return;
                    }
                    data.forEach(l => {
                        const badge = l.action === 'Time In' ? 'bg-emerald-100 text-emerald-800 border-emerald-200' : 'bg-rose-100 text-rose-800 border-rose-200';
                        tbody.innerHTML += `
                            <tr class="border-b border-slate-100 text-xs text-slate-600 hover:bg-emerald-50/20 transition-colors">
                                <td class="p-2.5 text-[11px]">${l.timestamp}</td>
                                <td class="p-2.5 font-medium text-slate-900">${l.normalized_name} <span class="text-slate-400 text-[11px]">(${l.student_id})</span></td>
                                <td class="p-2.5"><span class="px-2 py-0.5 rounded text-[10px] bg-slate-100 text-slate-600">${l.college}</span></td>
                                <td class="p-2.5"><span class="px-2 py-0.5 rounded-md font-semibold text-[11px] border ${badge}">${l.action}</span></td>
                            </tr>`;
                    });
                })
                .catch(() => {});
        }

        setInterval(fetchLogs, 3000);

        // ---------- Edit visitor modal ----------
        const EDIT_MAX = 120;
        let editOriginal = { name: '', course: '' };
        let editTouched = false;

        function openEditModal(id, name, course, college) {
            document.getElementById('edit-id').value = id;
            document.getElementById('edit-name').value = name;
            document.getElementById('edit-course').value = course;
            document.getElementById('edit-display-id').innerText = id;
            document.getElementById('edit-display-category').innerText = college || '-';
            editOriginal = { name: name.trim(), course: course.trim() };
            editTouched = false;
            setFieldError('edit-name', 'edit-name-error', '');
            setFieldError('edit-course', 'edit-course-error', '');
            onEditInput();
            document.getElementById('edit-modal').classList.remove('hidden');
            setTimeout(() => document.getElementById('edit-name').focus(), 50);
        }

        function closeEditModal() {
            document.getElementById('edit-modal').classList.add('hidden');
        }

        function setFieldError(inputId, errorId, message) {
            const input = document.getElementById(inputId);
            const err = document.getElementById(errorId);
            const okClasses = ['border-slate-300', 'focus:border-emerald-600', 'focus:ring-emerald-500/20'];
            const badClasses = ['border-rose-400', 'focus:border-rose-500', 'focus:ring-rose-500/20'];
            if (message) {
                err.innerText = message;
                err.classList.remove('hidden');
                input.classList.remove(...okClasses);
                input.classList.add(...badClasses);
            } else {
                err.classList.add('hidden');
                input.classList.remove(...badClasses);
                input.classList.add(...okClasses);
            }
        }

        function validateEditForm() {
            const name = document.getElementById('edit-name').value.trim();
            const course = document.getElementById('edit-course').value.trim();
            let nameMsg = '';
            let courseMsg = '';
            if (!name) nameMsg = 'Full name is required.';
            else if (name.length < 2) nameMsg = 'Full name must be at least 2 characters.';
            if (!course) courseMsg = 'Course, department, or address is required.';
            setFieldError('edit-name', 'edit-name-error', nameMsg);
            setFieldError('edit-course', 'edit-course-error', courseMsg);
            return !nameMsg && !courseMsg;
        }

        function onEditInput() {
            const name = document.getElementById('edit-name').value;
            const course = document.getElementById('edit-course').value;
            document.getElementById('edit-name-count').innerText = `${name.length}/${EDIT_MAX}`;
            document.getElementById('edit-course-count').innerText = `${course.length}/${EDIT_MAX}`;

            if (editTouched) validateEditForm();

            const dirty = name.trim() !== editOriginal.name || course.trim() !== editOriginal.course;
            const btn = document.getElementById('save-edit-btn');
            const state = document.getElementById('edit-state');
            btn.disabled = !dirty;
            state.innerText = dirty ? 'Unsaved changes' : 'No changes yet';
            state.className = 'mr-auto text-[11px] font-medium ' + (dirty ? 'text-amber-600' : 'text-slate-400');
        }

        function saveStudentEdit(event) {
            event.preventDefault();
            editTouched = true;
            if (!validateEditForm()) return;

            const id = document.getElementById('edit-id').value;
            const newName = document.getElementById('edit-name').value.trim();
            const newCourse = document.getElementById('edit-course').value.trim();
            const btn = document.getElementById('save-edit-btn');
            btn.disabled = true;
            btn.innerText = 'Saving...';

            fetch('/api/students/edit', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ student_id: id, normalized_name: newName, course_year: newCourse })
            })
            .then(r => r.json())
            .then(data => {
                showToast(data.message || 'Updated successfully!', 'success');
                closeEditModal();
                fetchStudents();
                btn.innerText = 'Save Changes';
            })
            .catch(() => {
                showToast('Failed to update. Please try again.', 'error');
                btn.innerText = 'Save Changes';
                btn.disabled = false;
            });
        }

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeEditModal();
        });

        function manualTime(id, action) {
            fetch('/api/logs/manual', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ student_id: id, action: action })
            })
            .then(r => r.json())
            .then(data => {
                showToast(data.message || `${action} recorded successfully!`, 'success');
                fetchLogs();
            })
            .catch(() => {
                showToast(`Failed to record ${action}.`, 'error');
            });
        }

        // ---------- Hamburger menu ----------
        function toggleNavMenu(event) {
            event.stopPropagation();
            const panel = document.getElementById('nav-menu-panel');
            const open = panel.classList.toggle('hidden') === false;
            document.getElementById('nav-menu-btn').setAttribute('aria-expanded', String(open));
        }

        function closeNavMenu() {
            document.getElementById('nav-menu-panel').classList.add('hidden');
            document.getElementById('nav-menu-btn').setAttribute('aria-expanded', 'false');
        }

        document.addEventListener('click', (e) => {
            if (!e.target.closest('#nav-menu-panel')) closeNavMenu();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeNavMenu();
        });

        window.onload = () => {
            document.getElementById('category-filter').value = currentCollege;
            fetchStudents();
            fetchLogs();
        };
    </script>
</head>
<body class="text-slate-800 antialiased min-h-screen">
    
    <!-- FLOATING TOAST NOTIFICATION CONTAINER -->
    <div id="toast-container" class="fixed top-5 right-5 z-[9999] flex flex-col gap-2.5 pointer-events-none max-w-sm w-full"></div>

    <div class="max-w-7xl mx-auto p-4 md:p-8">
        
        <!-- HEADER -->
        <header class="mb-6 border-b border-emerald-900/10 pb-5 flex items-center justify-between gap-4">
            <div class="flex items-center gap-3.5">
                <div class="w-10 h-10 rounded-xl bg-emerald-700 text-white flex items-center justify-center shadow-md shadow-emerald-800/15">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"></path></svg>
                </div>
                <div>
                    <h1 class="text-2xl font-bold text-emerald-950 tracking-tight">GuardGate Admin Station</h1>
                    
                </div>
            </div>
            <!-- HAMBURGER MENU -->
            <div class="relative shrink-0">
                <button type="button" id="nav-menu-btn" onclick="toggleNavMenu(event)" aria-haspopup="true" aria-expanded="false" aria-controls="nav-menu-panel" aria-label="Open menu" class="w-10 h-10 rounded-xl bg-emerald-800 hover:bg-emerald-900 text-white flex items-center justify-center shadow-sm border border-emerald-900/20 transition focus:outline-none focus:ring-4 focus:ring-emerald-500/20">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path></svg>
                </button>
                <div id="nav-menu-panel" role="menu" class="hidden absolute right-0 mt-2 w-48 bg-white rounded-xl shadow-xl shadow-slate-900/10 border border-slate-200 py-1.5 z-40">
                    <a href="/scanner" role="menuitem" class="flex items-center gap-2.5 px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-emerald-50 hover:text-emerald-900 transition-colors">
                        <svg class="w-4 h-4 text-emerald-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                        Student View
                    </a>
                </div>
            </div>
        </header>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            <!-- TIME LOGS LIST -->
            <div class="lg:col-span-1 bg-white rounded-2xl p-5 shadow-sm border border-emerald-900/10 max-h-[750px] flex flex-col">
                <h2 class="text-sm font-bold mb-3 text-emerald-950 flex items-center justify-between">
                    Attendance History
                    
                </h2>
                <div class="overflow-y-auto flex-grow">
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="border-b border-slate-100 text-[11px] text-slate-400 uppercase font-semibold">
                                <th class="p-2">Time</th>
                                <th class="p-2">Name</th>
                                <th class="p-2">Role/Col</th>
                                <th class="p-2">Action</th>
                            </tr>
                        </thead>
                        <tbody id="logs-tbody"></tbody>
                    </table>
                </div>
            </div>

            <!-- VISITOR / STUDENT MANAGEMENT LIST -->
            <div class="lg:col-span-2 bg-white rounded-2xl p-6 shadow-sm border border-emerald-900/10">
                <!-- RECORD CONTROLS: one category dropdown + independent search -->
                <div class="flex flex-col sm:flex-row sm:items-end gap-3 mb-5 pb-5 border-b border-slate-100">
                    <div class="sm:w-52 shrink-0">
                        <label for="category-filter" class="block text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-1.5">Category</label>
                        <div class="relative">
                            <select id="category-filter" autocomplete="off" onchange="filterCollege(this.value)" class="w-full appearance-none bg-white border border-slate-300 rounded-xl pl-3.5 pr-9 py-2 text-xs font-medium text-slate-800 shadow-sm cursor-pointer outline-none transition hover:border-slate-400 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600">
                                <option value="ALL">All Records</option>
                                <optgroup label="Colleges">
                                    <option value="CCIS">CCIS</option>
                                    <option value="CAS">CAS</option>
                                    <option value="COE">COE</option>
                                    <option value="CBEA">CBEA</option>
                                    <option value="CAFSD">CAFSD</option>
                                    <option value="CHS">CHS</option>
                                    <option value="COL">COL</option>
                                    <option value="CASAT">CASAT</option>
                                    <option value="CIT">CIT</option>
                                    <option value="CTE">CTE</option>
                                </optgroup>
                                <optgroup label="Other Categories">
                                    <option value="Faculty">Faculty</option>
                                    <option value="Parent">Parent</option>
                                    <option value="Others">Others</option>
                                </optgroup>
                            </select>
                            <svg class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                        </div>
                    </div>
                    <div class="flex-1 min-w-0">
                        <label for="search-input" class="block text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-1.5">Search</label>
                        <div class="relative">
                            <svg class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                            <input type="text" id="search-input" oninput="fetchStudents()" placeholder="Search name" class="w-full bg-white border border-slate-300 rounded-xl pl-9 pr-3.5 py-2 text-xs text-slate-800 shadow-sm outline-none transition hover:border-slate-400 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600">
                        </div>
                    </div>
                </div>

                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="border-b border-slate-100 text-xs text-slate-400 font-semibold uppercase">
                                <th class="p-3">ID Number</th>
                                <th class="p-3">Full Name</th>
                                <th class="p-3">Category</th>
                                <th class="p-3">Course / Dept / Address</th>
                                <th class="p-3">Actions</th>
                            </tr>
                        </thead>
                        <tbody id="students-tbody"></tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <!-- EDIT VISITOR MODAL -->
    <div id="edit-modal" class="hidden fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/50 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="edit-modal-title" onmousedown="if (event.target === this) closeEditModal()">
        <div class="bg-white rounded-2xl shadow-2xl shadow-slate-900/20 w-full max-w-lg max-h-[94vh] flex flex-col overflow-hidden border border-slate-200">

            <div class="shrink-0 px-6 py-4 border-b border-slate-100 flex items-start justify-between gap-4">
                <div class="flex items-start gap-3">
                    <div class="w-9 h-9 rounded-xl bg-emerald-700 text-white flex items-center justify-center shadow-sm shrink-0">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path></svg>
                    </div>
                    <div>
                        <h3 id="edit-modal-title" class="text-sm font-bold text-slate-900">Edit Visitor Information</h3>
                        <p class="text-xs text-slate-500 mt-0.5">Update the details below, then save your changes.</p>
                    </div>
                </div>
                <button type="button" onclick="closeEditModal()" aria-label="Close" class="text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg p-1.5 transition-colors">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            </div>

            <form id="edit-form" onsubmit="saveStudentEdit(event)" novalidate class="flex flex-col min-h-0">
                <input type="hidden" id="edit-id">

                <div class="px-6 py-5 space-y-5 overflow-y-auto min-h-0">
                    <div class="grid grid-cols-2 gap-3">
                        <div class="rounded-xl bg-slate-50 border border-slate-200 px-3.5 py-2.5">
                            <p class="text-[10px] font-semibold uppercase tracking-wider text-slate-400">ID Number</p>
                            <p id="edit-display-id" class="text-sm font-semibold text-slate-900 mt-0.5 break-all"></p>
                        </div>
                        <div class="rounded-xl bg-slate-50 border border-slate-200 px-3.5 py-2.5">
                            <p class="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Category</p>
                            <p id="edit-display-category" class="text-sm font-semibold text-slate-900 mt-0.5"></p>
                        </div>
                    </div>

                    <div>
                        <div class="flex items-center justify-between mb-1.5">
                            <label for="edit-name" class="text-xs font-semibold text-slate-700">Full Name <span class="text-rose-600">*</span></label>
                            <span id="edit-name-count" class="text-[11px] text-slate-400">0/120</span>
                        </div>
                        <input type="text" id="edit-name" maxlength="120" autocomplete="off" oninput="onEditInput()" class="w-full border border-slate-300 rounded-xl px-3.5 py-2.5 text-sm text-slate-900 shadow-sm outline-none transition focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600">
                        <p class="text-[11px] text-slate-500 mt-1.5">Format: Surname, First Name, Middle Name, Suffix</p>
                        <p id="edit-name-error" role="alert" class="hidden text-[11px] font-medium text-rose-600 mt-1.5"></p>
                    </div>

                    <div>
                        <div class="flex items-center justify-between mb-1.5">
                            <label for="edit-course" class="text-xs font-semibold text-slate-700">Course &amp; Year / Department / Address <span class="text-rose-600">*</span></label>
                            <span id="edit-course-count" class="text-[11px] text-slate-400">0/120</span>
                        </div>
                        <input type="text" id="edit-course" maxlength="120" autocomplete="off" oninput="onEditInput()" class="w-full border border-slate-300 rounded-xl px-3.5 py-2.5 text-sm text-slate-900 shadow-sm outline-none transition focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600">
                        <p id="edit-course-error" role="alert" class="hidden text-[11px] font-medium text-rose-600 mt-1.5"></p>
                    </div>
                </div>

                <div class="shrink-0 px-6 py-4 bg-slate-50/70 border-t border-slate-100 flex items-center gap-3">
                    <p id="edit-state" class="mr-auto text-[11px] font-medium text-slate-400">No changes yet</p>
                    <button type="button" onclick="closeEditModal()" class="px-4 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-300 rounded-xl hover:bg-slate-50 transition shadow-sm">
                        Cancel
                    </button>
                    <button type="submit" id="save-edit-btn" disabled class="px-4 py-2 text-xs font-semibold text-white bg-emerald-700 rounded-xl hover:bg-emerald-800 focus:ring-4 focus:ring-emerald-500/20 transition shadow-sm disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-emerald-700">
                        Save Changes
                    </button>
                </div>
            </form>
        </div>
    </div>

</body>
</html>
"""

@guard_bp.route('/guard')
def guard_page():
    return render_template_string(HTML_GUARD_STATION)

@guard_bp.route('/api/students')
def get_students():
    college = request.args.get('college', 'ALL')
    q = request.args.get('q', '').strip()

    query = supabase.table("visitors").select("*")
    if college != 'ALL':
        query = query.eq("college", college)
    if q:
        query = query.or_(f"normalized_name.ilike.%{q}%,student_id.ilike.%{q}%,course_year.ilike.%{q}%")
    
    return jsonify(query.execute().data)

@guard_bp.route('/api/logs')
def get_logs():
    college = request.args.get('college', 'ALL')
    query = supabase.table("logs").select("*")
    if college != 'ALL':
        query = query.eq("college", college)
    
    return jsonify(query.order("id", desc=True).limit(30).execute().data)

@guard_bp.route('/api/students/edit', methods=['POST'])
def edit_student():
    data = request.json
    s_id = data.get('student_id')
    normalized_name = data.get('normalized_name')
    course_year = data.get('course_year')

    supabase.table("visitors").update({
        "normalized_name": normalized_name,
        "course_year": course_year
    }).eq("student_id", s_id).execute()

    return jsonify({"message": "Student information updated successfully!"})

@guard_bp.route('/api/logs/manual', methods=['POST'])
def manual_log():
    data = request.json
    s_id = data.get('student_id')
    action = data.get('action')

    res = supabase.table("visitors").select("*").eq("student_id", s_id).execute()
    if not res.data:
        return jsonify({"message": "Student not found."}), 404

    student = res.data[0]
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    supabase.table("logs").insert({
        "student_id": s_id,
        "normalized_name": student["normalized_name"],
        "college": student["college"],
        "course_year": student["course_year"],
        "action": action,
        "timestamp": timestamp
    }).execute()

    return jsonify({"message": f"Successfully recorded {action} for {student['normalized_name']}!"})