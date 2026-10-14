import io
import re
import time
import logging
from collections import OrderedDict
from datetime import datetime
from flask import Blueprint, render_template_string, request, jsonify, send_file
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
        let selectedLogs = new Set();
        let visibleLogCount = 0;
        let confirmAction = null;

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
            selectedLogs.clear();
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
                    const visibleIds = new Set(data.map(l => String(l.id)));
                    selectedLogs.forEach(id => { if (!visibleIds.has(id)) selectedLogs.delete(id); });
                    visibleLogCount = data.length;
                    tbody.innerHTML = '';
                    if (data.length === 0) {
                        tbody.innerHTML = `<tr><td colspan="6" class="p-6 text-center text-slate-400 text-xs">No time logs recorded yet.</td></tr>`;
                        updateLogToolbar();
                        return;
                    }
                    data.forEach(l => {
                        const badge = l.action === 'Time In' ? 'bg-emerald-100 text-emerald-800 border-emerald-200' : 'bg-rose-100 text-rose-800 border-rose-200';
                        const isSelected = selectedLogs.has(String(l.id));
                        tbody.innerHTML += `
                            <tr class="border-b border-slate-100 text-xs text-slate-600 hover:bg-emerald-50/20 transition-colors ${isSelected ? 'bg-emerald-50/60' : ''}">
                                <td class="p-2.5 w-8"><input type="checkbox" data-log-id="${l.id}" ${isSelected ? 'checked' : ''} onchange="toggleLogSelect(this)" aria-label="Select log entry" class="w-3.5 h-3.5 rounded cursor-pointer accent-emerald-700"></td>
                                <td class="p-2.5 text-[11px]">${l.timestamp}</td>
                                <td class="p-2.5 font-medium text-slate-900">${l.normalized_name} <span class="text-slate-400 text-[11px]">(${l.student_id})</span></td>
                                <td class="p-2.5"><span class="px-2 py-0.5 rounded text-[10px] bg-slate-100 text-slate-600">${l.college}</span></td>
                                <td class="p-2.5"><span class="px-2 py-0.5 rounded-md font-semibold text-[11px] border ${badge}">${l.action}</span></td>
                                <td class="p-2.5 w-8">
                                    <button type="button" data-log-id="${l.id}" onclick="requestDeleteOne(this)" aria-label="Delete log entry" title="Delete this entry" class="text-slate-400 hover:text-rose-600 hover:bg-rose-50 p-1 rounded-lg transition-colors">
                                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                                    </button>
                                </td>
                            </tr>`;
                    });
                    updateLogToolbar();
                })
                .catch(() => {});
        }

        function updateLogToolbar() {
            const n = selectedLogs.size;
            const label = document.getElementById('logs-selected-count');
            const selectedBtn = document.getElementById('delete-selected-btn');
            const allBtn = document.getElementById('delete-all-btn');
            const master = document.getElementById('logs-select-all');
            label.innerText = n > 0 ? `${n} selected` : 'Select entries to delete';
            label.className = 'text-[11px] font-medium ' + (n > 0 ? 'text-emerald-800' : 'text-slate-400');
            selectedBtn.classList.toggle('hidden', n === 0);
            selectedBtn.innerText = `Delete selected (${n})`;
            allBtn.innerText = currentCollege === 'ALL' ? 'Clear all' : `Clear all ${currentCollege}`;
            allBtn.disabled = visibleLogCount === 0;
            master.disabled = visibleLogCount === 0;
            master.checked = visibleLogCount > 0 && n === visibleLogCount;
            master.indeterminate = n > 0 && n < visibleLogCount;
        }

        function toggleLogSelect(box) {
            const id = box.dataset.logId;
            if (box.checked) selectedLogs.add(id); else selectedLogs.delete(id);
            box.closest('tr').classList.toggle('bg-emerald-50/60', box.checked);
            updateLogToolbar();
        }

        function toggleSelectAll(checked) {
            document.querySelectorAll('#logs-tbody input[data-log-id]').forEach(box => {
                box.checked = checked;
                if (checked) selectedLogs.add(box.dataset.logId); else selectedLogs.delete(box.dataset.logId);
                box.closest('tr').classList.toggle('bg-emerald-50/60', checked);
            });
            updateLogToolbar();
        }

        function openConfirmModal(title, message, okLabel, action) {
            document.getElementById('confirm-title').innerText = title;
            document.getElementById('confirm-message').innerText = message;
            const ok = document.getElementById('confirm-ok-btn');
            ok.innerText = okLabel;
            ok.disabled = false;
            confirmAction = action;
            document.getElementById('confirm-modal').classList.remove('hidden');
            setTimeout(() => document.getElementById('confirm-cancel-btn').focus(), 50);
        }

        function closeConfirmModal() {
            document.getElementById('confirm-modal').classList.add('hidden');
            confirmAction = null;
        }

        function runConfirmAction() {
            if (!confirmAction) return;
            const action = confirmAction;
            const ok = document.getElementById('confirm-ok-btn');
            ok.disabled = true;
            ok.innerText = 'Deleting...';
            action().finally(closeConfirmModal);
        }

        function deleteLogs(url, body) {
            return fetch(url, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)
            })
            .then(r => r.json().catch(() => ({})).then(data => ({ ok: r.ok, data })))
            .then(({ ok, data }) => {
                if (!ok) throw new Error(data.message || 'Failed to delete logs. Please try again.');
                showToast(data.message, data.deleted > 0 ? 'success' : 'info');
            })
            .catch(err => showToast(err.message || 'Failed to delete logs. Please try again.', 'error'))
            .finally(fetchLogs);
        }

        function requestDeleteOne(btn) {
            const id = btn.dataset.logId;
            openConfirmModal(
                'Delete this log entry?',
                'This entry will be permanently removed from the attendance history.',
                'Delete',
                () => deleteLogs('/api/logs/delete', { ids: [id] })
            );
        }

        function requestDeleteSelected() {
            const ids = Array.from(selectedLogs);
            if (ids.length === 0) return;
            openConfirmModal(
                ids.length === 1 ? 'Delete 1 log entry?' : `Delete ${ids.length} log entries?`,
                'The selected entries will be permanently removed from the attendance history. This cannot be undone.',
                `Delete ${ids.length}`,
                () => deleteLogs('/api/logs/delete', { ids })
            );
        }

        function requestDeleteAll() {
            const scope = currentCollege === 'ALL' ? 'every attendance log' : `every ${currentCollege} attendance log`;
            const college = currentCollege;
            openConfirmModal(
                currentCollege === 'ALL' ? 'Clear all logs?' : `Clear all ${currentCollege} logs?`,
                `This will permanently delete ${scope}, including older entries that are not shown in the list. This cannot be undone.`,
                'Delete all',
                () => deleteLogs('/api/logs/delete-all', { college })
            );
        }

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeConfirmModal();
        });

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

        // ---------- PDF export ----------
        const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
        let exportMode = 'range';
        let exportStudentMap = {};
        let exportReady = false;

        function initExportPeriod() {
            if (exportReady) return;
            const now = new Date();
            ['export-from', 'export-to'].forEach(prefix => {
                const m = document.getElementById(prefix + '-month');
                const y = document.getElementById(prefix + '-year');
                
                m.innerHTML = '';
                MONTH_NAMES.forEach((name, i) => m.add(new Option(name, String(i + 1).padStart(2, '0'))));
                m.value = String(now.getMonth() + 1).padStart(2, '0');
                y.value = String(now.getFullYear());
            });
            exportReady = true;
        }

        function getExportPeriod(prefix) {
            return document.getElementById(prefix + '-year').value + '-' + document.getElementById(prefix + '-month').value;
        }

        function showExportError(message) {
            const el = document.getElementById('export-error');
            el.innerText = message;
            el.classList.toggle('hidden', !message);
        }

        function onExportAllDatesChange() {
            const allDates = document.getElementById('export-all-dates').checked;
            ['export-from-month', 'export-from-year', 'export-to-month', 'export-to-year'].forEach(id => {
                document.getElementById(id).disabled = allDates;
            });
        }

        function setExportMode(mode) {
            exportMode = mode;
            const on = 'bg-white text-emerald-900 shadow-sm';
            const off = 'text-slate-500 hover:text-slate-700';
            document.getElementById('export-tab-range').className = 'px-3 py-2 text-xs font-semibold rounded-lg transition ' + (mode === 'range' ? on : off);
            document.getElementById('export-tab-student').className = 'px-3 py-2 text-xs font-semibold rounded-lg transition ' + (mode === 'student' ? on : off);
            document.getElementById('export-student-group').classList.toggle('hidden', mode !== 'student');
            if (mode === 'student') {
                onExportAllDatesChange();
            } else {
                ['export-from-month', 'export-from-year', 'export-to-month', 'export-to-year'].forEach(id => {
                    document.getElementById(id).disabled = false;
                });
            }
            document.getElementById('export-hint').innerText = mode === 'range'
                ? 'One row per visitor with total entries (Time In) and exits (Time Out) for the selected months, inclusive.'
                : 'One report for a single visitor with entries and exits counted per day. Untick "Include all dates" to limit it to a month range.';
            showExportError('');
        }

        function openExportModal(mode) {
            closeNavMenu();
            initExportPeriod();
            setExportMode(mode);
            document.getElementById('export-modal').classList.remove('hidden');
            if (mode === 'student') setTimeout(() => document.getElementById('export-student').focus(), 50);
        }

        function closeExportModal() {
            document.getElementById('export-modal').classList.add('hidden');
        }

        function onExportStudentInput() {
            const input = document.getElementById('export-student');
            const q = input.value.trim();
            showExportError('');
            if (exportStudentMap[input.value] || q.length < 2) return;
            fetch(`/api/students?college=ALL&q=${encodeURIComponent(q)}`)
                .then(r => r.json())
                .then(rows => {
                    const list = document.getElementById('export-student-list');
                    list.innerHTML = '';
                    exportStudentMap = {};
                    rows.slice(0, 20).forEach(s => {
                        const label = `${s.normalized_name} (${s.student_id})`;
                        exportStudentMap[label] = s.student_id;
                        const opt = document.createElement('option');
                        opt.value = label;
                        list.appendChild(opt);
                    });
                })
                .catch(() => {});
        }

        function submitExport(event) {
            event.preventDefault();
            showExportError('');
            const params = new URLSearchParams({ mode: exportMode });

            if (exportMode === 'student') {
                const studentId = exportStudentMap[document.getElementById('export-student').value];
                if (!studentId) {
                    showExportError('Choose a visitor from the suggestions list.');
                    return;
                }
                params.set('student_id', studentId);
            }

            const allDates = exportMode === 'student' && document.getElementById('export-all-dates').checked;
            if (!allDates) {
                const from = getExportPeriod('export-from');
                const to = getExportPeriod('export-to');
                if (from > to) {
                    showExportError('no no no bad!');
                    return;
                }
                params.set('from', from);
                params.set('to', to);
            }

            const btn = document.getElementById('export-submit-btn');
            btn.disabled = true;
            btn.innerText = 'Generating...';

            fetch('/api/logs/export-pdf?' + params.toString())
                .then(res => {
                    if (!res.ok) {
                        return res.json().catch(() => ({})).then(d => { throw new Error(d.message || 'Failed to generate the PDF.'); });
                    }
                    const disposition = res.headers.get('Content-Disposition') || '';
                    const match = /filename="?([^";]+)"?/.exec(disposition);
                    return res.blob().then(blob => ({ blob, filename: match ? match[1] : 'guardgate_logs.pdf' }));
                })
                .then(({ blob, filename }) => {
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    setTimeout(() => URL.revokeObjectURL(url), 1000);
                    showToast('PDF report downloaded.', 'success');
                    closeExportModal();
                })
                .catch(err => showExportError(err.message || 'Failed to generate the PDF.'))
                .finally(() => {
                    btn.disabled = false;
                    btn.innerText = 'Download PDF';
                });
        }

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeExportModal();
        });

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
                <div id="nav-menu-panel" role="menu" class="hidden absolute right-0 mt-2 w-64 bg-white rounded-xl shadow-xl shadow-slate-900/10 border border-slate-200 py-1.5 z-40">
                    <p class="px-4 pt-1.5 pb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">Reports</p>
                    <button type="button" role="menuitem" onclick="openExportModal('range')" class="w-full text-left flex items-center gap-2.5 px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-emerald-50 hover:text-emerald-900 transition-colors">
                        <svg class="w-4 h-4 text-emerald-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
                        Export Logs by Month Range (PDF)
                    </button>
                    <button type="button" role="menuitem" onclick="openExportModal('student')" class="w-full text-left flex items-center gap-2.5 px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-emerald-50 hover:text-emerald-900 transition-colors">
                        <svg class="w-4 h-4 text-emerald-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg>
                        Export Logs per Student (PDF)
                    </button>
                    <div class="my-1.5 border-t border-slate-100"></div>
                    <p class="px-4 pt-1 pb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">Navigate</p>
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
                <div class="flex flex-wrap items-center justify-between gap-2 mb-3 min-h-[32px]">
                    <span id="logs-selected-count" class="text-[11px] font-medium text-slate-400">Select entries to delete</span>
                    <div class="flex items-center gap-1.5">
                        <button type="button" id="delete-selected-btn" onclick="requestDeleteSelected()" class="hidden px-3 py-1.5 text-[11px] font-semibold text-white bg-rose-600 rounded-lg hover:bg-rose-700 focus:ring-4 focus:ring-rose-500/20 transition shadow-sm">Delete selected</button>
                        <button type="button" id="delete-all-btn" onclick="requestDeleteAll()" disabled class="px-3 py-1.5 text-[11px] font-semibold text-rose-700 bg-white border border-rose-200 rounded-lg hover:bg-rose-50 focus:ring-4 focus:ring-rose-500/20 transition disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-white">Clear all</button>
                    </div>
                </div>
                <div class="overflow-y-auto flex-grow">
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="border-b border-slate-100 text-[11px] text-slate-400 uppercase font-semibold">
                                <th class="p-2 w-8"><input type="checkbox" id="logs-select-all" onchange="toggleSelectAll(this.checked)" disabled aria-label="Select all log entries" class="w-3.5 h-3.5 rounded cursor-pointer accent-emerald-700 disabled:cursor-not-allowed disabled:opacity-40"></th>
                                <th class="p-2">Time</th>
                                <th class="p-2">Name</th>
                                <th class="p-2">Role/Col</th>
                                <th class="p-2">Action</th>
                                <th class="p-2 w-8"><span class="sr-only">Delete</span></th>
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

    <!-- EXPORT PDF MODAL -->
    <div id="export-modal" class="hidden fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/50 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="export-modal-title" onmousedown="if (event.target === this) closeExportModal()">
        <div class="bg-white rounded-2xl shadow-2xl shadow-slate-900/20 w-full max-w-lg max-h-[94vh] flex flex-col overflow-hidden border border-slate-200">

            <div class="shrink-0 px-6 py-4 border-b border-slate-100 flex items-start justify-between gap-4">
                <div class="flex items-start gap-3">
                    <div class="w-9 h-9 rounded-xl bg-emerald-700 text-white flex items-center justify-center shadow-sm shrink-0">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                    </div>
                    <div>
                        <h3 id="export-modal-title" class="text-sm font-bold text-slate-900">Export Attendance Logs (PDF)</h3>
                        <p class="text-xs text-slate-500 mt-0.5">Reports show entry and exit counts instead of every log line.</p>
                    </div>
                </div>
                <button type="button" onclick="closeExportModal()" aria-label="Close" class="text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg p-1.5 transition-colors">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            </div>

            <form id="export-form" onsubmit="submitExport(event)" novalidate class="flex flex-col min-h-0">
                <div class="px-6 py-5 space-y-5 overflow-y-auto min-h-0">

                    <div class="grid grid-cols-2 gap-1 p-1 rounded-xl bg-slate-100">
                        <button type="button" id="export-tab-range" onclick="setExportMode('range')" class="px-3 py-2 text-xs font-semibold rounded-lg transition">By Month Range</button>
                        <button type="button" id="export-tab-student" onclick="setExportMode('student')" class="px-3 py-2 text-xs font-semibold rounded-lg transition">Per Student</button>
                    </div>

                    <div id="export-student-group">
                        <label for="export-student" class="block text-xs font-semibold text-slate-700 mb-1.5">Visitor <span class="text-rose-600">*</span></label>
                        <input type="text" id="export-student" list="export-student-list" autocomplete="off" oninput="onExportStudentInput()" placeholder="Type a name or ID, then pick from the list" class="w-full border border-slate-300 rounded-xl px-3.5 py-2.5 text-sm text-slate-900 shadow-sm outline-none transition focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600">
                        <datalist id="export-student-list"></datalist>
                        <label class="mt-3 flex items-center gap-2 text-xs font-medium text-slate-700 cursor-pointer select-none">
                            <input type="checkbox" id="export-all-dates" checked onchange="onExportAllDatesChange()" class="w-3.5 h-3.5 rounded cursor-pointer accent-emerald-700">
                            Include all dates
                        </label>
                    </div>

                    <div id="export-period-group" class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <p class="text-xs font-semibold text-slate-700 mb-1.5">From</p>
                            <div class="grid grid-cols-5 gap-2">
                                <select id="export-from-month" aria-label="From month" class="col-span-3 border border-slate-300 rounded-xl px-3 py-2 text-xs bg-white shadow-sm outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 disabled:opacity-50 disabled:cursor-not-allowed"></select>
                                <input type="number" id="export-from-year" aria-label="From year" placeholder="YYYY" min="2000" max="2100" class="col-span-2 border border-slate-300 rounded-xl px-3 py-2 text-xs bg-white shadow-sm outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 disabled:opacity-50 disabled:cursor-not-allowed">
                            </div>
                        </div>
                        <div>
                            <p class="text-xs font-semibold text-slate-700 mb-1.5">To</p>
                            <div class="grid grid-cols-5 gap-2">
                                <select id="export-to-month" aria-label="To month" class="col-span-3 border border-slate-300 rounded-xl px-3 py-2 text-xs bg-white shadow-sm outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 disabled:opacity-50 disabled:cursor-not-allowed"></select>
                                <input type="number" id="export-to-year" aria-label="To year" placeholder="YYYY" min="2000" max="2100" class="col-span-2 border border-slate-300 rounded-xl px-3 py-2 text-xs bg-white shadow-sm outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 disabled:opacity-50 disabled:cursor-not-allowed">
                            </div>
                        </div>
                    </div>

                    <p id="export-hint" class="text-[11px] text-slate-500 leading-relaxed"></p>
                    <p id="export-error" role="alert" class="hidden text-[11px] font-medium text-rose-600"></p>
                </div>

                <div class="shrink-0 px-6 py-4 bg-slate-50/70 border-t border-slate-100 flex items-center justify-end gap-3">
                    <button type="button" onclick="closeExportModal()" class="px-4 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-300 rounded-xl hover:bg-slate-50 transition shadow-sm">Cancel</button>
                    <button type="submit" id="export-submit-btn" class="px-4 py-2 text-xs font-semibold text-white bg-emerald-700 rounded-xl hover:bg-emerald-800 focus:ring-4 focus:ring-emerald-500/20 transition shadow-sm disabled:opacity-50 disabled:cursor-not-allowed">Download PDF</button>
                </div>
            </form>
        </div>
    </div>

    <!-- CONFIRM DELETE MODAL -->
    <div id="confirm-modal" class="hidden fixed inset-0 z-[60] flex items-center justify-center p-4 bg-slate-950/50 backdrop-blur-sm" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title" aria-describedby="confirm-message" onmousedown="if (event.target === this) closeConfirmModal()">
        <div class="bg-white rounded-2xl shadow-2xl shadow-slate-900/20 w-full max-w-sm overflow-hidden border border-slate-200">
            <div class="px-6 pt-6 pb-5 flex items-start gap-3.5">
                <div class="w-10 h-10 rounded-xl bg-rose-50 text-rose-600 border border-rose-200 flex items-center justify-center shrink-0">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                </div>
                <div class="min-w-0">
                    <h3 id="confirm-title" class="text-sm font-bold text-slate-900"></h3>
                    <p id="confirm-message" class="text-xs text-slate-500 mt-1.5 leading-relaxed"></p>
                </div>
            </div>
            <div class="px-6 py-4 bg-slate-50/70 border-t border-slate-100 flex items-center justify-end gap-3">
                <button type="button" id="confirm-cancel-btn" onclick="closeConfirmModal()" class="px-4 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-300 rounded-xl hover:bg-slate-50 transition shadow-sm">Cancel</button>
                <button type="button" id="confirm-ok-btn" onclick="runConfirmAction()" class="px-4 py-2 text-xs font-semibold text-white bg-rose-600 rounded-xl hover:bg-rose-700 focus:ring-4 focus:ring-rose-500/20 transition shadow-sm disabled:opacity-50 disabled:cursor-not-allowed">Delete</button>
            </div>
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

@guard_bp.route('/api/logs/delete', methods=['POST'])
def delete_logs():
    data = request.get_json(silent=True) or {}
    raw_ids = data.get('ids')
    if not isinstance(raw_ids, list) or not raw_ids:
        return jsonify({"message": "No log entries selected.", "deleted": 0}), 400

    ids = [str(i).strip() for i in raw_ids if i is not None and str(i).strip()]
    if not ids or len(ids) > 100:
        return jsonify({"message": "Invalid selection.", "deleted": 0}), 400

    try:
        res = supabase.table("logs").delete().in_("id", ids).execute()
    except Exception:
        logging.exception("Failed to delete selected logs")
        return jsonify({"message": "Failed to delete log entries.", "deleted": 0}), 500

    deleted = len(res.data or [])
    if deleted == 0:
        message = "No entries were deleted. They may have already been removed."
    elif deleted == 1:
        message = "Log entry deleted."
    else:
        message = f"{deleted} log entries deleted."
    return jsonify({"message": message, "deleted": deleted})

@guard_bp.route('/api/logs/delete-all', methods=['POST'])
def delete_all_logs():
    data = request.get_json(silent=True) or {}
    college = data.get('college', 'ALL')

    try:
        query = supabase.table("logs").delete().not_.is_("id", "null")
        if college != 'ALL':
            query = query.eq("college", college)
        res = query.execute()
    except Exception:
        logging.exception("Failed to delete all logs")
        return jsonify({"message": "Failed to clear logs.", "deleted": 0}), 500

    deleted = len(res.data or [])
    if deleted == 0:
        message = "There were no logs to delete."
    elif college == 'ALL':
        message = f"All logs cleared ({deleted} deleted)."
    else:
        message = f"All {college} logs cleared ({deleted} deleted)."
    return jsonify({"message": message, "deleted": deleted})


# ==================== PDF export ====================

def _month_bounds(from_month, to_month):
    """Turn 'YYYY-MM' + 'YYYY-MM' into (start, end_exclusive) timestamp strings."""
    start_dt = datetime.strptime(from_month, "%Y-%m")
    to_dt = datetime.strptime(to_month, "%Y-%m")
    if start_dt > to_dt:
        raise ValueError("The start month cannot be later than the end month.")
    end_year, end_month = (to_dt.year + 1, 1) if to_dt.month == 12 else (to_dt.year, to_dt.month + 1)
    end_dt = datetime(end_year, end_month, 1)
    return (
        start_dt.strftime("%Y-%m-%d 00:00:00"),
        end_dt.strftime("%Y-%m-%d 00:00:00"),
        start_dt,
        to_dt,
    )

def _fetch_logs_for_export(start=None, end=None, student_id=None):
    """Read every matching log row, paging past Supabase's 1000-row response cap."""
    rows = []
    page_size = 1000
    offset = 0
    while True:
        query = supabase.table("logs").select("*")
        if start:
            query = query.gte("timestamp", start)
        if end:
            query = query.lt("timestamp", end)
        if student_id:
            query = query.eq("student_id", student_id)
        batch = query.order("id").range(offset, offset + page_size - 1).execute().data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows

def _pretty_name(raw):
    """'Santos, Maria, N/A, Jr.' -> 'Santos, Maria Jr.' (drops empty N/A parts)."""
    parts = [p.strip() for p in (raw or "").split(",")]
    parts = [p for p in parts if p and p.upper() != "N/A"]
    if len(parts) <= 1:
        return parts[0] if parts else (raw or "-")
    return f"{parts[0]}, {' '.join(parts[1:])}"

def _build_export_pdf(mode, rows, period_label, student=None):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    green = colors.HexColor("#047857")
    dark = colors.HexColor("#064e3b")
    zebra = colors.HexColor("#f1f7f3")
    grid = colors.HexColor("#d1d5db")

    base = getSampleStyleSheet()
    title_style = ParagraphStyle("t", parent=base["Title"], fontName="Helvetica-Bold", fontSize=17, textColor=dark, alignment=0, spaceAfter=2)
    sub_style = ParagraphStyle("s", parent=base["Normal"], fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#475569"), leading=13)
    cell_style = ParagraphStyle("c", parent=base["Normal"], fontName="Helvetica", fontSize=8.5, leading=11)
    head_style = ParagraphStyle("h", parent=cell_style, fontName="Helvetica-Bold", textColor=colors.white)
    head_center = ParagraphStyle("hc", parent=head_style, alignment=1)

    total_in = sum(1 for r in rows if r.get("action") == "Time In")
    total_out = sum(1 for r in rows if r.get("action") == "Time Out")
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    story = []
    if mode == "student":
        story.append(Paragraph("GuardGate Visitor Attendance Report", title_style))
        story.append(Paragraph(f"Visitor: <b>{_esc(_pretty_name(student.get('normalized_name')))}</b>", sub_style))
        story.append(Paragraph(f"ID Number: {_esc(student.get('student_id'))} &nbsp;|&nbsp; Category: {_esc(student.get('college'))} &nbsp;|&nbsp; {_esc(student.get('course_year') or '-')}", sub_style))
    else:
        story.append(Paragraph("GuardGate Attendance Summary", title_style))
    story.append(Paragraph(f"Period: {_esc(period_label)} &nbsp;|&nbsp; Generated: {generated}", sub_style))
    story.append(Spacer(1, 4 * mm))

    if mode == "student":
        by_day = OrderedDict()
        for r in rows:
            day = str(r.get("timestamp") or "")[:10]
            entry = by_day.setdefault(day, [0, 0])
            if r.get("action") == "Time In":
                entry[0] += 1
            elif r.get("action") == "Time Out":
                entry[1] += 1
        story.append(Paragraph(f"Total entries: <b>{total_in}</b> &nbsp;|&nbsp; Total exits: <b>{total_out}</b> &nbsp;|&nbsp; Days with activity: <b>{len(by_day)}</b>", sub_style))
        story.append(Spacer(1, 4 * mm))

        data = [[Paragraph("Date", head_style), Paragraph("Entries", head_center), Paragraph("Exits", head_center)]]
        for day, (n_in, n_out) in by_day.items():
            try:
                label = datetime.strptime(day, "%Y-%m-%d").strftime("%Y-%m-%d (%a)")
            except ValueError:
                label = day or "-"
            data.append([Paragraph(label, cell_style), str(n_in), str(n_out)])
        data.append([Paragraph("<b>Total</b>", cell_style), str(total_in), str(total_out)])
        col_widths = [90 * mm, 40 * mm, 40 * mm]
        numeric_from = 1
    else:
        people = OrderedDict()
        for r in rows:
            key = r.get("student_id")
            p = people.setdefault(key, {"name": r.get("normalized_name"), "college": r.get("college"), "in": 0, "out": 0})
            if r.get("action") == "Time In":
                p["in"] += 1
            elif r.get("action") == "Time Out":
                p["out"] += 1
        ordered = sorted(people.items(), key=lambda kv: (kv[1]["name"] or "").lower())
        story.append(Paragraph(f"Visitors: <b>{len(ordered)}</b> &nbsp;|&nbsp; Total entries: <b>{total_in}</b> &nbsp;|&nbsp; Total exits: <b>{total_out}</b>", sub_style))
        story.append(Spacer(1, 4 * mm))

        data = [[Paragraph(h, head_center if h in ("No.", "Entries", "Exits") else head_style) for h in ("No.", "ID Number", "Full Name", "Category", "Entries", "Exits")]]
        for i, (sid, p) in enumerate(ordered, start=1):
            data.append([
                str(i),
                Paragraph(_esc(sid), cell_style),
                Paragraph(_esc(_pretty_name(p["name"])), cell_style),
                Paragraph(_esc(p["college"]), cell_style),
                str(p["in"]),
                str(p["out"]),
            ])
        data.append(["", "", Paragraph("<b>Total</b>", cell_style), "", str(total_in), str(total_out)])
        col_widths = [12 * mm, 30 * mm, 70 * mm, 28 * mm, 20 * mm, 20 * mm]
        numeric_from = 4

    if len(data) == 2:
        story.append(Paragraph("No attendance records were found for the selected filters.", sub_style))
    else:
        table = Table(data, colWidths=col_widths, repeatRows=1)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), green),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 8.5),
            ("ALIGN", (numeric_from, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.4, grid),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, zebra]),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#dcefe3")),
            ("FONTNAME", (numeric_from, -1), (-1, -1), "Helvetica-Bold"),
        ]
        if mode != "student":
            style.append(("ALIGN", (0, 0), (0, -1), "CENTER"))
        table.setStyle(TableStyle(style))
        story.append(table)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(doc.leftMargin, 10 * mm, "GuardGate Admin Station")
        canvas.drawRightString(A4[0] - doc.rightMargin, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
                            title="GuardGate Attendance Report", author="GuardGate")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return buffer

def _esc(value):
    return str(value if value is not None else "-").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

@guard_bp.route('/api/logs/export-pdf')
def export_logs_pdf():
    mode = request.args.get('mode', 'range')
    from_month = request.args.get('from', '').strip()
    to_month = request.args.get('to', '').strip()
    student_id = request.args.get('student_id', '').strip()

    if mode not in ('range', 'student'):
        return jsonify({"message": "Invalid export type."}), 400

    start = end = None
    period_label = "All dates"
    if mode == 'range' or from_month or to_month:
        if not from_month or not to_month:
            return jsonify({"message": "Select both a start month and an end month."}), 400
        try:
            start, end, start_dt, to_dt = _month_bounds(from_month, to_month)
        except ValueError as e:
            msg = str(e) if "cannot be later" in str(e) else "Invalid month selection."
            return jsonify({"message": msg}), 400
        if from_month == to_month:
            period_label = start_dt.strftime("%B %Y")
        else:
            period_label = f"{start_dt.strftime('%B %Y')} to {to_dt.strftime('%B %Y')}"

    student = None
    if mode == 'student':
        if not student_id:
            return jsonify({"message": "Choose a visitor to export."}), 400
        found = supabase.table("visitors").select("*").eq("student_id", student_id).execute().data
        if not found:
            return jsonify({"message": "Visitor not found."}), 404
        student = found[0]

    try:
        from reportlab.lib.pagesizes import A4  # noqa: F401  (availability check)
    except ImportError:
        return jsonify({"message": "PDF export needs the reportlab package. Run: pip install reportlab"}), 500

    try:
        rows = _fetch_logs_for_export(start, end, student_id if mode == 'student' else None)
        if not rows:
            if mode == 'student':
                who = _pretty_name(student.get('normalized_name'))
                where = "on record" if period_label == "All dates" else f"for {period_label}"
                return jsonify({"message": f"No attendance logs found for {who} {where}. Nothing to export."}), 404
            return jsonify({"message": f"No attendance logs found for {period_label}. Nothing to export."}), 404
        pdf = _build_export_pdf(mode, rows, period_label, student)
    except Exception:
        logging.exception("Failed to build PDF export")
        return jsonify({"message": "Failed to generate the PDF report."}), 500

    if mode == 'student':
        safe_id = re.sub(r'[^A-Za-z0-9_-]', '_', student_id)
        filename = f"guardgate_{safe_id}_logs.pdf"
    elif from_month == to_month:
        filename = f"guardgate_logs_{from_month}.pdf"
    else:
        filename = f"guardgate_logs_{from_month}_to_{to_month}.pdf"

    return send_file(pdf, mimetype='application/pdf', as_attachment=True, download_name=filename)