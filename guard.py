import io
import re
import time
import logging
from collections import OrderedDict
from datetime import datetime
from flask import Blueprint, render_template_string, request, jsonify, send_file
from supabase import create_client, Client
from flask import session, redirect, abort
from datetime import datetime, timezone, timedelta

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
        let visitorCache = {};

        function escAttr(v) {
            return String(v === null || v === undefined ? '' : v).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        }

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
            hideSummaryHover();
            const query = document.getElementById('search-input').value;
            fetch(`/api/students?college=${currentCollege}&q=${encodeURIComponent(query)}`)
                .then(r => r.json())
                .then(data => {
                    const tbody = document.getElementById('students-tbody');
                    tbody.innerHTML = '';
                    visitorCache = {};
                    data.forEach(s => { visitorCache[s.student_id] = s; });
                    if (data.length === 0) {
                        tbody.innerHTML = `<tr><td colspan="5" class="p-6 text-center text-slate-400 text-xs">No visitor records found.</td></tr>`;
                        return;
                    }
                    data.forEach(s => {
                        const safeId = (s.student_id || '').replace(/'/g, "\\'");

                        let tagClass = 'bg-emerald-50 text-emerald-800 border-emerald-200';
                        if (s.college === 'Parent') tagClass = 'bg-purple-50 text-purple-800 border-purple-200';
                        else if (s.college === 'Faculty') tagClass = 'bg-amber-50 text-amber-800 border-amber-200';
                        else if (s.college === 'Others') tagClass = 'bg-slate-100 text-slate-700 border-slate-200';

                        tbody.innerHTML += `
                            <tr class="border-b border-slate-100 text-xs text-slate-700 hover:bg-emerald-50/30 transition-colors">
                                <td class="p-3 font-semibold text-slate-900">${s.student_id}</td>
                                <td class="p-3 font-medium cursor-help" tabindex="0" data-id="${escAttr(s.student_id)}" onmouseenter="showSummaryHover(this)" onmouseleave="scheduleHideSummary()" onfocus="showSummaryHover(this)" onblur="hideSummaryHover()">${s.normalized_name}</td>
                                <td class="p-3"><span class="border text-[11px] px-2.5 py-0.5 rounded-full font-semibold ${tagClass}">${s.college}</span></td>
                                <td class="p-3 text-slate-600">${s.course_year || '-'}</td>
                                <td class="p-3 flex items-center gap-1.5">
                                    <button type="button" data-id="${escAttr(s.student_id)}" onclick="openEditModal(this.dataset.id)" class="text-xs bg-emerald-50 text-emerald-800 border border-emerald-200/80 px-2.5 py-1 rounded-lg hover:bg-emerald-100 font-medium transition">Edit Info</button>
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

        // ---------- Edit visitor modal (mirrors the registration form) ----------
        const EDIT_COLLEGES = ['CCIS', 'CAS', 'COE', 'CBEA', 'CAFSD', 'CHS', 'COL', 'CASAT', 'CIT', 'CTE'];
        const EDIT_SUFFIXES = ['N/A', 'Jr.', 'Sr.', 'III', 'IV'];
        const EDIT_GROUPS = {
            Student: 'edit-group-student',
            Parent: 'edit-group-parent',
            Faculty: 'edit-group-faculty',
            Others: 'edit-group-others'
        };
        const EDIT_HINTS = {
            Student: 'Student record: Student ID, College, Year Level, and Course.',
            Parent: 'Parent record: requires Surname, First Name, Middle Name, and Address. Suffix is optional.',
            Faculty: 'Faculty record: requires Name fields, College, and Department.',
            Others: 'Visitor / Guest record: requires Name fields and Address or Purpose of visit.'
        };
        let editSnapshot = '';
        let editTouched = false;

        function editVal(id) { return document.getElementById(id).value; }
        function editSet(id, value) { document.getElementById(id).value = (value === null || value === undefined) ? '' : value; }

        // Rebuild the registration-form fields from a stored visitor row
        // (name = "Surname, First, Middle|N/A, Suffix"; course_year depends on the category).
        function parseVisitorRecord(v) {
            const parts = (v.normalized_name || '').split(',').map(p => p.trim());
            const info = {
                type: 'Student',
                surname: parts[0] || '',
                fname: parts[1] || '',
                mname: (parts[2] && parts[2].toUpperCase() !== 'N/A') ? parts[2] : '',
                suffix: EDIT_SUFFIXES.includes(parts[3]) ? parts[3] : 'N/A',
                college: '', year: '', program: '', address: '', facultyCollege: '', department: ''
            };
            const cy = (v.course_year || '').trim();
            if (v.college === 'Parent' || v.college === 'Faculty' || v.college === 'Others') info.type = v.college;

            if (info.type === 'Student') {
                info.college = EDIT_COLLEGES.includes(v.college) ? v.college : '';
                const m = /^(.*) - Year ([1-4])$/.exec(cy);
                if (m) { info.program = m[1]; info.year = m[2]; } else { info.program = cy; }
            } else if (info.type === 'Faculty') {
                const idx = cy.indexOf(' - ');
                const fc = idx > -1 ? cy.slice(0, idx) : '';
                if (EDIT_COLLEGES.includes(fc)) { info.facultyCollege = fc; info.department = cy.slice(idx + 3); }
                else { info.department = cy; }
            } else {
                info.address = cy;
            }
            return info;
        }

        // Only the fields that belong to the selected category are collected (same as registration).
        function collectEditForm() {
            const type = document.getElementById('edit-user-type').value;
            const d = {
                user_type: type,
                surname: editVal('edit-surname').trim(),
                student_id: editVal('edit-student-id').trim(),
                fname: editVal('edit-fname').trim(),
                mname: editVal('edit-mname').trim(),
                suffix: editVal('edit-suffix')
            };
            if (type === 'Student') {
                d.college = editVal('edit-college');
                d.year_level = editVal('edit-year');
                d.course = editVal('edit-course-program').trim().toUpperCase();
            } else if (type === 'Parent') {
                d.parent_address = editVal('edit-parent-address').trim();
            } else if (type === 'Faculty') {
                d.faculty_college = editVal('edit-faculty-college');
                d.department = editVal('edit-department').trim();
            } else {
                d.other_address = editVal('edit-other-address').trim();
            }
            return d;
        }

        function applyEditType(type) {
            Object.keys(EDIT_GROUPS).forEach(t => {
                document.getElementById(EDIT_GROUPS[t]).classList.toggle('hidden', t !== type);
            });
            document.getElementById('edit-mname-label').innerHTML = type === 'Parent'
                ? 'Middle Name <span class="text-rose-600">*</span>'
                : 'Middle Name <span class="text-slate-400 font-normal">(Optional)</span>';
            document.getElementById('edit-type-hint').innerText = EDIT_HINTS[type] || '';
        }

        function handleEditUserTypeChange(type) {
            applyEditType(type);
            clearEditErrors();
            editTouched = false;
            refreshEditState();
        }

        function openEditModal(id) {
            const v = visitorCache[id];
            if (!v) { showToast('Visitor record not found. Please refresh the list.', 'error'); return; }
            const info = parseVisitorRecord(v);

            editSet('edit-id', id);
            document.getElementById('edit-display-id').innerText = id;
            editSet('edit-user-type', info.type);
            editSet('edit-surname', info.surname);
            editSet('edit-fname', info.fname);
            editSet('edit-mname', info.mname);
            editSet('edit-suffix', info.suffix);
            editSet('edit-college', info.college);
            editSet('edit-student-id', id);
            editSet('edit-year', info.year);
            editSet('edit-course-program', info.program);
            editSet('edit-parent-address', info.type === 'Parent' ? info.address : '');
            editSet('edit-faculty-college', info.facultyCollege);
            editSet('edit-department', info.department);
            editSet('edit-other-address', info.type === 'Others' ? info.address : '');

            applyEditType(info.type);
            clearEditErrors();
            editTouched = false;
            editSnapshot = JSON.stringify(collectEditForm());
            refreshEditState();
            document.getElementById('edit-modal').classList.remove('hidden');
            setTimeout(() => document.getElementById('edit-surname').focus(), 50);
        }

        function closeEditModal() {
            document.getElementById('edit-modal').classList.add('hidden');
        }

        function clearEditErrors() {
            document.querySelectorAll('#edit-form .field-err').forEach(el => el.remove());
            document.querySelectorAll('#edit-form input, #edit-form select').forEach(el => {
                el.classList.remove('border-rose-400');
                if (!el.readOnly && el.type !== 'hidden') el.classList.add('border-slate-300');
            });
        }

        function setEditError(inputId, message) {
            const input = document.getElementById(inputId);
            input.classList.remove('border-slate-300');
            input.classList.add('border-rose-400');
            const err = document.createElement('p');
            err.className = 'field-err text-[11px] font-medium text-rose-600 mt-1';
            err.innerText = message;
            input.parentElement.appendChild(err);
        }

        function validateEditForm() {
            const type = editVal('edit-user-type');
            const rules = [
                ['edit-surname', 'Surname is required.'],
                ['edit-fname', 'First name is required.']
            ];
            if (type === 'Student') {
                rules.push(['edit-college', 'Select a college.'], ['edit-year', 'Select a year level.'], ['edit-course-program', 'Course / Program is required.']);
            } else if (type === 'Parent') {
                rules.push(['edit-mname', 'Middle name is required for parents.'], ['edit-parent-address', 'Home / residential address is required.']);
            } else if (type === 'Faculty') {
                rules.push(['edit-faculty-college', 'Select a college.'], ['edit-department', 'Department is required.']);
            } else {
                rules.push(['edit-other-address', 'Address or purpose of visit is required.']);
            }
            clearEditErrors();
            let ok = true;
            rules.forEach(([id, msg]) => {
                if (!editVal(id).trim()) { setEditError(id, msg); ok = false; }
            });
            return ok;
        }

        function refreshEditState() {
            const dirty = JSON.stringify(collectEditForm()) !== editSnapshot;
            const btn = document.getElementById('save-edit-btn');
            const state = document.getElementById('edit-state');
            btn.disabled = !dirty;
            state.innerText = dirty ? 'Unsaved changes' : 'No changes yet';
            state.className = 'mr-auto text-[11px] font-medium ' + (dirty ? 'text-amber-600' : 'text-slate-400');
        }

        function onEditInput() {
            if (editTouched) validateEditForm();
            refreshEditState();
        }

        function saveStudentEdit(event) {
            event.preventDefault();
            editTouched = true;
        if (!validateEditForm()) return;

    // Kunin ang original ID at ang form data
        const originalId = editVal('edit-id');
        const payload = Object.assign({ original_id: originalId }, collectEditForm());
    
        const btn = document.getElementById('save-edit-btn');
        btn.disabled = true;
        btn.innerText = 'Saving...';

    fetch('/api/students/edit', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    })
            .then(r => r.json().catch(() => ({})).then(data => ({ ok: r.ok, data })))
            .then(({ ok, data }) => {
                if (!ok) throw new Error(data.message || 'Failed to update. Please try again.');
                showToast(data.message || 'Updated successfully!', 'success');
                closeEditModal();
                fetchStudents();
                fetchLogs();
            })
            .catch(err => {
                showToast(err.message || 'Failed to update. Please try again.', 'error');
                btn.disabled = false;
            })
            .finally(() => { btn.innerText = 'Save Changes'; });
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
        .then(r => r.json().then(data => ({ ok: r.ok, data })))
        .then(({ ok, data }) => {
        if (!ok) {
            showToast(data.message || `Failed to record ${action}.`, 'error');
        } else {
            showToast(data.message || `${action} recorded successfully!`, 'success');
            fetchLogs();
        }
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
                ? 'One chart per day with a horizontal bar for each visitor stay, from Time In to Time Out, for the selected months (inclusive).'
                : 'One chart for a single visitor with a row per day and a bar for each stay. Untick "Include all dates" to limit it to a month range.';
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
                    return res.blob().then(blob => ({ blob, filename: match ? match[1] : 'guardgate.pdf' }));
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
                    showToast('download started.', 'success');
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

        let freqData = [];
        let freqInitialized = false;
        let freqRequestId = 0;

        function showFreqError(message) {
            const el = document.getElementById('freq-error');
            el.innerText = message;
            el.classList.toggle('hidden', !message);
        }

        function openFreqModal() {
            closeNavMenu();
            if (!freqInitialized) {
                const now = new Date();
                const current = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0');
                document.getElementById('freq-from').value = current;
                document.getElementById('freq-to').value = current;
                freqInitialized = true;
            }
            document.getElementById('freq-modal').classList.remove('hidden');
            loadFreqSummary();
            setTimeout(() => document.getElementById('freq-search').focus(), 50);
        }

        function closeFreqModal() {
            document.getElementById('freq-modal').classList.add('hidden');
        }

        function onFreqPeriodChange() {
            const allTime = document.getElementById('freq-all-time').checked;
            document.getElementById('freq-from').disabled = allTime;
            document.getElementById('freq-to').disabled = allTime;
            loadFreqSummary();
        }

        function loadFreqSummary() {
            const params = new URLSearchParams();
            if (!document.getElementById('freq-all-time').checked) {
                const from = document.getElementById('freq-from').value;
                const to = document.getElementById('freq-to').value;
                if (!from || !to) {
                    showFreqError('Select both a start month and an end month.');
                    return;
                }
                if (from > to) {
                    showFreqError('The start month cannot be later than the end month.');
                    return;
                }
                params.set('from', from);
                params.set('to', to);
            }
            showFreqError('');

            const requestId = ++freqRequestId;
            document.getElementById('freq-tbody').innerHTML = `<tr><td colspan="5" class="p-6 text-center text-slate-400 text-xs">Loading summary...</td></tr>`;

            fetch('/api/visit-summary?' + params.toString())
                .then(r => r.json().catch(() => ({})).then(data => ({ ok: r.ok, data })))
                .then(({ ok, data }) => {
                    if (requestId !== freqRequestId) return;
                    if (!ok) throw new Error(data.message || 'Failed to load the visit summary.');
                    freqData = (data.visitors || []).map((v, i) => Object.assign({ rank: i + 1 }, v));
                    document.getElementById('freq-total').innerText = data.total_entries || 0;
                    document.getElementById('freq-active').innerText = freqData.filter(v => v.entries > 0).length;
                    document.getElementById('freq-period').innerText = data.period || 'All time';
                    renderFreqTable();
                })
                .catch(err => {
                    if (requestId !== freqRequestId) return;
                    freqData = [];
                    document.getElementById('freq-total').innerText = 0;
                    document.getElementById('freq-active').innerText = 0;
                    showFreqError(err.message || 'Failed to load the visit summary.');
                    renderFreqTable();
                });
        }

        function renderFreqTable() {
            const q = document.getElementById('freq-search').value.trim().toLowerCase();
            const rows = freqData.filter(v => !q || (v.name || '').toLowerCase().includes(q) || (v.student_id || '').toLowerCase().includes(q));
            const tbody = document.getElementById('freq-tbody');

            if (rows.length === 0) {
                const message = freqData.length === 0 ? 'No visitors found.' : 'No visitors match your search.';
                tbody.innerHTML = `<tr><td colspan="5" class="p-6 text-center text-slate-400 text-xs">${message}</td></tr>`;
                return;
            }

            const maxEntries = Math.max(1, ...freqData.map(v => v.entries));
            tbody.innerHTML = rows.map(v => {
                const pct = Math.round((v.entries / maxEntries) * 100);
                return `
                    <tr class="border-b border-slate-100 text-xs text-slate-700 hover:bg-emerald-50/30 transition-colors">
                        <td class="p-2.5 text-slate-400 font-semibold">${v.rank}</td>
                        <td class="p-2.5 font-medium text-slate-900">${escAttr(v.name)} <span class="text-slate-400 text-[11px]">(${escAttr(v.student_id)})</span></td>
                        <td class="p-2.5"><span class="px-2 py-0.5 rounded text-[10px] bg-slate-100 text-slate-600">${escAttr(v.college)}</span></td>
                        <td class="p-2.5">
                            <div class="flex items-center gap-2.5">
                                <span class="w-8 text-sm font-bold text-emerald-900">${v.entries}</span>
                                <div class="h-1.5 w-24 rounded-full bg-slate-100 overflow-hidden"><div class="h-full rounded-full bg-emerald-600" style="width: ${pct}%"></div></div>
                            </div>
                        </td>
                        <td class="p-2.5 text-[11px] text-slate-600">${v.last_entry ? escAttr(v.last_entry) : '-'}</td>
                    </tr>`;
            }).join('');
        }

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeFreqModal();
        });

        let summaryHoverToken = 0;
        let summaryHoverTimer = null;
        let summaryHideTimer = null;
        let summaryAnchor = null;
        const summaryCache = {};
        const SUMMARY_CACHE_MS = 15000;

        function summaryStat(label, value) {
            return `<div class="rounded-lg border border-slate-200 bg-slate-50/60 px-2.5 py-2"><p class="text-[9px] font-semibold uppercase text-slate-400">${escAttr(label)}</p><p class="mt-0.5 text-xs font-bold text-slate-900">${escAttr(value)}</p></div>`;
        }

        function positionSummaryHover() {
            const card = document.getElementById('summary-hover');
            if (!summaryAnchor || card.classList.contains('hidden')) return;
            const rect = summaryAnchor.getBoundingClientRect();
            const width = card.offsetWidth;
            const height = card.offsetHeight;
            const left = Math.min(Math.max(8, rect.left), Math.max(8, window.innerWidth - width - 8));
            let top = rect.bottom + 6;
            if (top + height > window.innerHeight - 8) top = Math.max(8, rect.top - height - 6);
            card.style.left = left + 'px';
            card.style.top = top + 'px';
        }

        function resetSummaryCard(id, cached) {
            document.getElementById('summary-name').innerText = id;
            document.getElementById('summary-meta').innerText = [cached.college, cached.course_year].filter(Boolean).join(' | ');
            document.getElementById('summary-status').innerHTML = '';
            document.getElementById('summary-stats').innerHTML = '';
            document.getElementById('summary-last').classList.add('hidden');
            document.getElementById('summary-recent').innerHTML = '';
            document.getElementById('summary-recent-wrap').classList.add('hidden');
            document.getElementById('summary-empty').classList.add('hidden');
            document.getElementById('summary-note').classList.add('hidden');
            document.getElementById('summary-error').classList.add('hidden');
            document.getElementById('summary-loading').classList.remove('hidden');
        }

        function showSummaryHover(cell) {
            clearTimeout(summaryHoverTimer);
            clearTimeout(summaryHideTimer);
            if (summaryAnchor === cell) return;
            if (summaryAnchor) hideSummaryCard();
            const token = ++summaryHoverToken;
            summaryHoverTimer = setTimeout(() => loadSummaryHover(cell, token), 200);
        }

        function loadSummaryHover(cell, token) {
            if (token !== summaryHoverToken || !document.body.contains(cell)) return;
            const id = cell.dataset.id;
            const card = document.getElementById('summary-hover');
            summaryAnchor = cell;
            resetSummaryCard(id, visitorCache[id] || {});
            card.classList.remove('hidden');
            positionSummaryHover();

            const hit = summaryCache[id];
            if (hit && Date.now() - hit.at < SUMMARY_CACHE_MS) {
                renderSummary(hit.data);
                return;
            }

            fetch('/api/students/summary?student_id=' + encodeURIComponent(id))
                .then(r => r.json().catch(() => ({})).then(data => ({ ok: r.ok, data })))
                .then(({ ok, data }) => {
                    if (token !== summaryHoverToken) return;
                    if (!ok) throw new Error(data.message || 'Failed to load the visitor summary.');
                    summaryCache[id] = { at: Date.now(), data: data };
                    renderSummary(data);
                })
                .catch(err => {
                    if (token !== summaryHoverToken) return;
                    document.getElementById('summary-loading').classList.add('hidden');
                    const el = document.getElementById('summary-error');
                    el.innerText = err.message || 'Failed to load the visitor summary.';
                    el.classList.remove('hidden');
                    positionSummaryHover();
                });
        }

        function renderSummary(data) {
            document.getElementById('summary-loading').classList.add('hidden');
            document.getElementById('summary-name').innerText = data.name || data.student_id;
            document.getElementById('summary-meta').innerText = [data.student_id, data.college, data.course_year].filter(Boolean).join(' | ');

            if (!data.entries) {
                document.getElementById('summary-empty').classList.remove('hidden');
                positionSummaryHover();
                return;
            }

            if (data.status) {
                const inside = data.status === 'Inside';
                const cls = inside ? 'bg-emerald-100 text-emerald-800 border-emerald-200' : 'bg-rose-100 text-rose-800 border-rose-200';
                document.getElementById('summary-status').innerHTML = `<span class="px-2 py-0.5 rounded-full border text-[10px] font-semibold whitespace-nowrap ${cls}">${escAttr(data.status)}</span>`;
            }

            document.getElementById('summary-stats').innerHTML = [
                summaryStat('Entries', data.entries),
                summaryStat('Days', data.days),
                summaryStat('Total time', data.total_time),
                summaryStat('Avg stay', data.average_stay),
                summaryStat('Longest', data.longest_stay),
                summaryStat('Open stays', data.open_stays)
            ].join('');

            const last = document.getElementById('summary-last');
            last.innerText = 'Last visit: ' + (data.last_visit || '-');
            last.classList.remove('hidden');

            if (data.open_stays > 0 || data.unrecorded_exits > 0) {
                const parts = [];
                if (data.open_stays > 0) parts.push(`${data.open_stays} open stay(s) without Time Out are counted up to the end of that day.`);
                if (data.unrecorded_exits > 0) parts.push(`${data.unrecorded_exits} Time Out(s) have no matching Time In.`);
                const note = document.getElementById('summary-note');
                note.innerText = parts.join(' ');
                note.classList.remove('hidden');
            }

            const recent = data.recent || [];
            if (recent.length > 0) {
                document.getElementById('summary-recent').innerHTML = recent.map(r => `
                    <tr class="border-b border-slate-100 text-[11px] text-slate-700">
                        <td class="py-1.5 pr-2 font-medium text-slate-900">${escAttr(r.date)}</td>
                        <td class="py-1.5 pr-2">${escAttr(r.time_in)}</td>
                        <td class="py-1.5 pr-2">${r.open ? '<span class="text-amber-700 font-semibold">No Time Out</span>' : escAttr(r.time_out)}</td>
                        <td class="py-1.5 text-slate-600">${escAttr(r.duration)}</td>
                    </tr>`).join('');
                document.getElementById('summary-recent-wrap').classList.remove('hidden');
            }
            positionSummaryHover();
        }

        function hideSummaryCard() {
            clearTimeout(summaryHoverTimer);
            clearTimeout(summaryHideTimer);
            summaryHoverToken++;
            summaryAnchor = null;
            const card = document.getElementById('summary-hover');
            if (card) card.classList.add('hidden');
        }

        function hideSummaryHover() {
            hideSummaryCard();
        }

        // Cursor entered the card: keep it open
        function holdSummaryHover() {
            clearTimeout(summaryHideTimer);
        }

        // Cursor left the name or the card: short grace period so it can cross from one to the other
        function scheduleHideSummary() {
            if (!summaryAnchor) { hideSummaryCard(); return; }
            clearTimeout(summaryHideTimer);
            summaryHideTimer = setTimeout(hideSummaryCard, 150);
        }


        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') hideSummaryHover();
        });
        window.addEventListener('scroll', hideSummaryHover, true);

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
                        Export by Month Range (PDF)
                    </button>
                    <button type="button" role="menuitem" onclick="openExportModal('student')" class="w-full text-left flex items-center gap-2.5 px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-emerald-50 hover:text-emerald-900 transition-colors">
                        <svg class="w-4 h-4 text-emerald-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg>
                        Export per visitor (PDF)
                    </button>
                    <div class="my-1.5 border-t border-slate-100"></div>
                    <p class="px-4 pt-1 pb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">Navigate</p>
                    <a href="/scanner" role="menuitem" class="flex items-center gap-2.5 px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-emerald-50 hover:text-emerald-900 transition-colors">
                        <svg class="w-4 h-4 text-emerald-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                        Student View
                    </a>
                    <a href="/admin-login" role="menuitem" class="flex items-center gap-2.5 px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-emerald-50 hover:text-emerald-900 transition-colors">
                        <svg class="w-4 h-4 text-emerald-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5.121 17.804A13.937 13.937 0 0112 16c2.5 0 4.847.655 6.879 1.804M15 10a3 3 0 11-6 0 3 3 0 016 0zm6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                        Admin Dashboard
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
                                <th class="p-2">College</th>
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

    <!-- EDIT VISITOR MODAL (mirrors the registration form: category first, then fields for that category) -->
    <div id="edit-modal" class="hidden fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/50 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="edit-modal-title" onmousedown="if (event.target === this) closeEditModal()">
        <div class="bg-white rounded-2xl shadow-2xl shadow-slate-900/20 w-full max-w-lg max-h-[94vh] flex flex-col overflow-hidden border border-slate-200">

            <div class="shrink-0 px-6 py-4 border-b border-slate-100 flex items-start justify-between gap-4">
                <div class="flex items-start gap-3">
                    <div class="w-9 h-9 rounded-xl bg-emerald-700 text-white flex items-center justify-center shadow-sm shrink-0">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path></svg>
                    </div>
                    <div>
                        <h3 id="edit-modal-title" class="text-sm font-bold text-slate-900">Edit Visitor</h3>
                        <p class="text-xs text-slate-500 mt-0.5">ID Number: <span id="edit-display-id" class="font-semibold text-slate-700">-</span></p>
                    </div>
                </div>
                <button type="button" onclick="closeEditModal()" aria-label="Close" class="text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg p-1.5 transition-colors">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            </div>

            <form id="edit-form" onsubmit="saveStudentEdit(event)" novalidate class="flex flex-col min-h-0">
                <input type="hidden" id="edit-id">

                <div class="px-6 py-5 space-y-4 overflow-y-auto min-h-0">
                    <!-- USER TYPE SELECTOR -->
                    <div class="p-3 rounded-xl bg-emerald-50/70 border border-emerald-200/80">
                        <label for="edit-user-type" class="block text-xs font-bold uppercase tracking-wider text-emerald-900 mb-1.5">User Type <span class="text-rose-600">*</span></label>
                    <select id="edit-user-type" disabled tabindex="-1" class="w-full border border-slate-200 bg-slate-50 text-slate-500 rounded-lg px-3.5 py-2 text-sm font-semibold outline-none cursor-not-allowed">
                        <option value="Student">Student</option>
                        <option value="Parent">Parent</option>
                        <option value="Faculty">Faculty</option>
                        <option value="Others">Others</option>
                    </select>
                        <p id="edit-type-hint" class="text-[11px] text-emerald-800/80 mt-1.5 font-medium"></p>
                    </div>

                    <!-- NAME FIELDS (COMMON TO ALL) -->
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div class="space-y-1">
                            <label for="edit-surname" class="block text-[11px] font-semibold text-slate-700">Surname <span class="text-rose-600">*</span></label>
                            <input type="text" id="edit-surname" oninput="onEditInput()" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600">
                        </div>
                        <div class="space-y-1">
                            <label for="edit-fname" class="block text-[11px] font-semibold text-slate-700">First Name <span class="text-rose-600">*</span></label>
                            <input type="text" id="edit-fname" oninput="onEditInput()" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600">
                        </div>
                        <div class="space-y-1">
                            <label id="edit-mname-label" for="edit-mname" class="block text-[11px] font-semibold text-slate-700">Middle Name <span class="text-slate-400 font-normal">(Optional)</span></label>
                            <input type="text" id="edit-mname" oninput="onEditInput()" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600">
                        </div>
                        <div class="space-y-1">
                            <label for="edit-suffix" class="block text-[11px] font-semibold text-slate-700">Suffix</label>
                            <select id="edit-suffix" onchange="onEditInput()" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 cursor-pointer">
                                <option value="N/A">N/A</option>
                                <option value="Jr.">Jr.</option>
                                <option value="Sr.">Sr.</option>
                                <option value="III">III</option>
                                <option value="IV">IV</option>
                            </select>
                        </div>
                    </div>

                    <!-- STUDENT FIELDS -->
                    <div id="edit-group-student" class="pt-3 border-t border-slate-100 grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div class="space-y-1 md:col-span-2">
                            <label for="edit-college" class="block text-[11px] font-semibold text-slate-700">College <span class="text-rose-600">*</span></label>
                            <select id="edit-college" onchange="onEditInput()" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 cursor-pointer">
                                <option value="">Select College...</option>
                                <option value="CCIS">CCIS : College of Computing and Information Sciences</option>
                                <option value="CAS">CAS : College of Arts and Sciences</option>
                                <option value="COE">COE : College of Engineering</option>
                                <option value="CBEA">CBEA : College of Business, Economics and Accountancy</option>
                                <option value="CAFSD">CAFSD : College of Agriculture, Forestry and Sustainable Development</option>
                                <option value="CHS">CHS : College of Health Sciences</option>
                                <option value="COL">COL : College of Law</option>
                                <option value="CASAT">CASAT : College of Aquatic Sciences and Applied Technology</option>
                                <option value="CIT">CIT : College of Industrial Technology</option>
                                <option value="CTE">CTE : College of Teacher Education</option>
                            </select>
                        </div>
                        <div class="space-y-1">
                            <label for="edit-student-id" class="block text-[11px] font-semibold text-slate-700">Student ID <span class="text-rose-600">*</span></label>
                            <input type="text" id="edit-student-id" oninput="onEditInput()" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600">
                        </div>
                        <div class="space-y-1">
                            <label for="edit-year" class="block text-[11px] font-semibold text-slate-700">Year Level <span class="text-rose-600">*</span></label>
                            <select id="edit-year" onchange="onEditInput()" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 cursor-pointer">
                                <option value="">Select Year...</option>
                                <option value="1">1</option>
                                <option value="2">2</option>
                                <option value="3">3</option>
                                <option value="4">4</option>
                            </select>
                        </div>
                        <div class="space-y-1 md:col-span-2">
                            <label for="edit-course-program" class="block text-[11px] font-semibold text-slate-700">Course / Program <span class="text-rose-600">*</span></label>
                            <input type="text" id="edit-course-program" maxlength="40" placeholder="e.g. BSCS" oninput="onEditInput()" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm uppercase placeholder:normal-case outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600">
                        </div>
                    </div>

                    <!-- PARENT FIELDS -->
                    <div id="edit-group-parent" class="hidden pt-3 border-t border-slate-100 space-y-1">
                        <label for="edit-parent-address" class="block text-[11px] font-semibold text-slate-700">Home / Residential Address <span class="text-rose-600">*</span></label>
                        <input type="text" id="edit-parent-address" oninput="onEditInput()" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600">
                    </div>

                    <!-- FACULTY FIELDS -->
                    <div id="edit-group-faculty" class="hidden pt-3 border-t border-slate-100 grid grid-cols-1 gap-3">
                        <div class="space-y-1">
                            <label for="edit-faculty-college" class="block text-[11px] font-semibold text-slate-700">College <span class="text-rose-600">*</span></label>
                            <select id="edit-faculty-college" onchange="onEditInput()" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 cursor-pointer">
                                <option value="">Select College...</option>
                                <option value="CCIS">CCIS : College of Computing and Information Sciences</option>
                                <option value="CAS">CAS : College of Arts and Sciences</option>
                                <option value="COE">COE : College of Engineering</option>
                                <option value="CBEA">CBEA : College of Business, Economics and Accountancy</option>
                                <option value="CAFSD">CAFSD : College of Agriculture, Forestry and Sustainable Development</option>
                                <option value="CHS">CHS : College of Health Sciences</option>
                                <option value="COL">COL : College of Law</option>
                                <option value="CASAT">CASAT : College of Aquatic Sciences and Applied Technology</option>
                                <option value="CIT">CIT : College of Industrial Technology</option>
                                <option value="CTE">CTE : College of Teacher Education</option>
                            </select>
                        </div>
                        <div class="space-y-1">
                            <label for="edit-department" class="block text-[11px] font-semibold text-slate-700">Department <span class="text-rose-600">*</span></label>
                            <input type="text" id="edit-department" oninput="onEditInput()" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600">
                        </div>
                    </div>

                    <!-- OTHERS FIELDS -->
                    <div id="edit-group-others" class="hidden pt-3 border-t border-slate-100 space-y-1">
                        <label for="edit-other-address" class="block text-[11px] font-semibold text-slate-700">Address or Purpose of Visit <span class="text-rose-600">*</span></label>
                        <input type="text" id="edit-other-address" oninput="onEditInput()" class="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600">
                    </div>
                </div>

                <div class="shrink-0 px-6 py-4 bg-slate-50/70 border-t border-slate-100 flex items-center gap-3 justify-end">
                    <span id="edit-state" class="mr-auto text-[11px] font-medium text-slate-400">No changes yet</span>
                    <button type="button" onclick="closeEditModal()" class="px-4 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-300 rounded-xl hover:bg-slate-50 transition shadow-sm">Cancel</button>
                    <button type="submit" id="save-edit-btn" disabled class="px-4 py-2 text-xs font-semibold text-white bg-emerald-700 rounded-xl hover:bg-emerald-800 focus:ring-4 focus:ring-emerald-500/20 transition shadow-sm disabled:opacity-50 disabled:cursor-not-allowed">Save Changes</button>
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
                        <h3 id="export-modal-title" class="text-sm font-bold text-slate-900">Export Visit Timeline (PDF)</h3>
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
                        <button type="button" id="export-tab-student" onclick="setExportMode('student')" class="px-3 py-2 text-xs font-semibold rounded-lg transition">Per Visitor</button>
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

    <!-- VISIT FREQUENCY SUMMARY MODAL -->
    <div id="freq-modal" class="hidden fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/50 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="freq-modal-title" onmousedown="if (event.target === this) closeFreqModal()">
        <div class="bg-white rounded-2xl shadow-2xl shadow-slate-900/20 w-full max-w-3xl max-h-[94vh] flex flex-col overflow-hidden border border-slate-200">

            <div class="shrink-0 px-6 py-4 border-b border-slate-100 flex items-start justify-between gap-4">
                <div class="flex items-start gap-3">
                    <div class="w-9 h-9 rounded-xl bg-emerald-700 text-white flex items-center justify-center shadow-sm shrink-0">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>
                    </div>
                    <div>
                        <h3 id="freq-modal-title" class="text-sm font-bold text-slate-900">Visit Frequency Summary</h3>
                        <p class="text-xs text-slate-500 mt-0.5">Total dorm entries per visitor. Each Time In counts as one entry.</p>
                    </div>
                </div>
                <button type="button" onclick="closeFreqModal()" aria-label="Close" class="text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg p-1.5 transition-colors">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            </div>

            <div class="shrink-0 px-6 pt-4 pb-3 space-y-3 border-b border-slate-100">
                <div class="relative">
                    <svg class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-4.35-4.35M17 11a6 6 0 11-12 0 6 6 0 0112 0z"></path></svg>
                    <input type="text" id="freq-search" oninput="renderFreqTable()" autocomplete="off" placeholder="Search name or ID" class="w-full bg-white border border-slate-300 rounded-xl pl-9 pr-3.5 py-2 text-xs text-slate-800 shadow-sm outline-none transition hover:border-slate-400 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600">
                </div>
                <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
                    <label class="flex items-center gap-2 text-xs font-medium text-slate-700 cursor-pointer select-none">
                        <input type="checkbox" id="freq-all-time" checked onchange="onFreqPeriodChange()" class="w-3.5 h-3.5 rounded cursor-pointer accent-emerald-700">
                        All time
                    </label>
                    <div class="flex items-center gap-2">
                        <label for="freq-from" class="text-xs font-semibold text-slate-700">From</label>
                        <input type="month" id="freq-from" onchange="onFreqPeriodChange()" disabled class="border border-slate-300 rounded-xl px-3 py-1.5 text-xs bg-white shadow-sm outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 disabled:opacity-50 disabled:cursor-not-allowed">
                        <label for="freq-to" class="text-xs font-semibold text-slate-700">To</label>
                        <input type="month" id="freq-to" onchange="onFreqPeriodChange()" disabled class="border border-slate-300 rounded-xl px-3 py-1.5 text-xs bg-white shadow-sm outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600 disabled:opacity-50 disabled:cursor-not-allowed">
                    </div>
                </div>
                <p id="freq-error" role="alert" class="hidden text-[11px] font-medium text-rose-600"></p>
                <div class="flex flex-wrap items-center gap-2 text-[11px] font-semibold">
                    <span class="px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200">Total entries: <span id="freq-total">0</span></span>
                    <span class="px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 border border-slate-200">Visitors with entries: <span id="freq-active">0</span></span>
                    <span class="px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 border border-slate-200">Period: <span id="freq-period">All time</span></span>
                </div>
            </div>

            <div class="flex-1 min-h-0 overflow-y-auto px-6 pb-4">
                <table class="w-full text-left border-collapse">
                    <thead class="sticky top-0 bg-white">
                        <tr class="border-b border-slate-100 text-[11px] text-slate-400 uppercase font-semibold">
                            <th class="p-2.5 pt-3 w-10">Rank</th>
                            <th class="p-2.5 pt-3">Visitor</th>
                            <th class="p-2.5 pt-3">Category</th>
                            <th class="p-2.5 pt-3">Total Entries</th>
                            <th class="p-2.5 pt-3">Last Entry</th>
                        </tr>
                    </thead>
                    <tbody id="freq-tbody"></tbody>
                </table>
            </div>

            <div class="shrink-0 px-6 py-4 bg-slate-50/70 border-t border-slate-100 flex items-center justify-end">
                <button type="button" onclick="closeFreqModal()" class="px-4 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-300 rounded-xl hover:bg-slate-50 transition shadow-sm">Close</button>
            </div>
        </div>
    </div>

    <!-- VISITOR SUMMARY HOVER CARD -->
    <div id="summary-hover" class="hidden fixed z-[70] w-80 max-w-[calc(100vw-1rem)] rounded-2xl bg-white border border-slate-200 shadow-2xl shadow-slate-900/20 p-4" role="tooltip" onmouseenter="holdSummaryHover()" onmouseleave="scheduleHideSummary()">
        <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
                <p id="summary-name" class="text-sm font-bold text-slate-900 break-words"></p>
                <p id="summary-meta" class="text-[11px] text-slate-500 mt-0.5 break-words"></p>
            </div>
            <div id="summary-status" class="shrink-0"></div>
        </div>
        <p id="summary-loading" class="text-center text-slate-400 text-xs py-4">Loading summary...</p>
        <p id="summary-error" role="alert" class="hidden text-[11px] font-medium text-rose-600 mt-2"></p>
        <p id="summary-empty" class="hidden text-center text-slate-400 text-xs py-4">No attendance logs recorded for this visitor yet.</p>
        <div id="summary-stats" class="grid grid-cols-3 gap-2 mt-3"></div>
        <p id="summary-last" class="hidden text-[11px] text-slate-600 mt-2.5"></p>
        <p id="summary-note" class="hidden text-[10px] text-slate-500 mt-1.5"></p>
        <div id="summary-recent-wrap" class="hidden mt-3">
            <p class="text-[10px] font-semibold uppercase text-slate-400 mb-1">Recent visits</p>
            <table class="w-full text-left border-collapse">
                <tbody id="summary-recent"></tbody>
            </table>
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

EDIT_COLLEGE_CODES = ('CCIS', 'CAS', 'COE', 'CBEA', 'CAFSD', 'CHS', 'COL', 'CASAT', 'CIT', 'CTE')
EDIT_SUFFIXES = ('N/A', 'Jr.', 'Sr.', 'III', 'IV')

def _compose_visitor_record(data):
    """Rebuild normalized_name / college / course_year exactly like /register does.
    Returns (error_message, fields). error_message is None when the input is valid."""
    def field(key):
        return str(data.get(key) or '').strip()

    user_type = field('user_type') or 'Student'
    surname, fname, mname = field('surname'), field('fname'), field('mname')
    suffix = field('suffix') or 'N/A'
    if suffix not in EDIT_SUFFIXES:
        suffix = 'N/A'

    if user_type not in ('Student', 'Parent', 'Faculty', 'Others'):
        return "Invalid user type.", None
    if not surname or not fname:
        return "Surname and First Name are required!", None

    if user_type == 'Parent':
        address = field('parent_address')
        if not mname:
            return "Middle Name is required for Parents!", None
        if not address:
            return "Address is required for Parents!", None
        college, course = "Parent", address

    elif user_type == 'Faculty':
        faculty_college = field('faculty_college')
        department = field('department')
        if faculty_college not in EDIT_COLLEGE_CODES:
            return "College is required for Faculty!", None
        if not department:
            return "Department is required for Faculty!", None
        # Category stays "Faculty" so Guard filters keep working; the faculty's college is stored with the department
        college, course = "Faculty", f"{faculty_college} - {department}"

    elif user_type == 'Others':
        college, course = "Others", (field('other_address') or "Visitor")

    else:  # Student
        college = field('college')
        program = field('course').upper()
        year_level = field('year_level')
        if college not in EDIT_COLLEGE_CODES or not program or not year_level:
            return "College, Course, and Year Level are required!", None
        if year_level not in ('1', '2', '3', '4'):
            return "Year Level must be between 1 and 4!", None
        course = f"{program} - Year {year_level}"

    normalized_name = f"{surname}, {fname}, {mname or 'N/A'}, {suffix}"
    return None, {"normalized_name": normalized_name, "college": college, "course_year": course}

@guard_bp.route('/api/students/edit', methods=['POST'])
def edit_student():
    original_id = None
    try:
        data = request.get_json(silent=True) or {}
        original_id = data.get('original_id') or data.get('student_id')
        new_id = data.get('student_id')
        
        if not original_id or not new_id:
            return jsonify({"message": "Missing required fields."}), 400

        # I-compose ang bagong details ng visitor
        error, fields = _compose_visitor_record(data)
        if error:
            return jsonify({"message": error}), 400
            
        fields["student_id"] = new_id

        # Kung nagbago ang ID, i-check muna kung ginagamit na ng iba ang bagong ID
        if original_id != new_id:
            check_existing = supabase.table("visitors").select("student_id").eq("student_id", new_id).execute()
            if check_existing.data:
                return jsonify({"message": "Student ID already exists!"}), 400

        # I-update ang visitors table
        res = supabase.table("visitors").update(fields).eq("student_id", original_id).execute()

        if not res.data:
            return jsonify({"message": "Student not found."}), 404

        # Kung nagbago ang ID, i-update din sa logs table para hindi masira ang history
        if original_id != new_id:
            supabase.table("logs").update({"student_id": new_id}).eq("student_id", original_id).execute()

        return jsonify({"message": "Student information updated successfully!"})

    except Exception as e:
        logging.error(f"Failed to update student {original_id}: {e}")
        return jsonify({"message": "Internal server error. Please try again."}), 500

@guard_bp.route('/api/logs/manual', methods=['POST'])
def manual_log():
    data = request.json or {}
    s_id = data.get('student_id')
    action = data.get('action')

    if action not in ('Time In', 'Time Out'):
        return jsonify({"message": "Invalid action requested."}), 400

    res = supabase.table("visitors").select("*").eq("student_id", s_id).execute()
    if not res.data:
        return jsonify({"message": "Student/Visitor not found."}), 404

    student = res.data[0]

    last_log_res = supabase.table("logs") \
        .select("action") \
        .eq("student_id", s_id) \
        .order("id", desc=True) \
        .limit(1) \
        .execute()

    last_action = last_log_res.data[0]["action"] if last_log_res.data else None

    if action == "Time Out" and last_action != "Time In":
        return jsonify({
            "message": f"Cannot Time Out, is not timed in yet."
        }), 400

    if action == "Time In" and last_action == "Time In":
        return jsonify({
            "message": f"Cannot Time In, is already timed in."
        }), 400

    ph_tz = timezone(timedelta(hours=8))
    timestamp = datetime.now(ph_tz).strftime("%Y-%m-%d %I:%M:%S %p")

    supabase.table("logs").insert({
        "student_id": s_id,
        "normalized_name": student["normalized_name"],
        "college": student["college"],
        "course_year": student["course_year"],
        "action": action,
        "timestamp": timestamp
    }).execute()

    return jsonify({"message": f"Successfully recorded {action}!"})

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


def _fetch_all_visitors():
    rows = []
    page_size = 1000
    offset = 0
    while True:
        batch = supabase.table("visitors").select("*").order("student_id").range(offset, offset + page_size - 1).execute().data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows

@guard_bp.route('/api/visit-summary')
def visit_summary():
    from_month = request.args.get('from', '').strip()
    to_month = request.args.get('to', '').strip()

    clip = None
    fetch_start = fetch_end = None
    period_label = "All time"
    if from_month or to_month:
        if not from_month or not to_month:
            return jsonify({"message": "Select both a start month and an end month."}), 400
        try:
            start, end, start_dt, to_dt = _month_bounds(from_month, to_month)
        except ValueError as e:
            msg = str(e) if "cannot be later" in str(e) else "Invalid month selection."
            return jsonify({"message": msg}), 400
        fmt = "%Y-%m-%d %H:%M:%S"
        clip = (datetime.strptime(start, fmt), datetime.strptime(end, fmt))
        fetch_start = (clip[0] - timedelta(days=1)).strftime(fmt)
        fetch_end = (clip[1] + timedelta(days=1)).strftime(fmt)
        if from_month == to_month:
            period_label = start_dt.strftime("%B %Y")
        else:
            period_label = f"{start_dt.strftime('%B %Y')} to {to_dt.strftime('%B %Y')}"

    try:
        visitors = _fetch_all_visitors()
        rows = _fetch_logs_for_export(fetch_start, fetch_end)
    except Exception:
        logging.exception("Failed to build visit summary")
        return jsonify({"message": "Failed to load the visit summary."}), 500

    people = OrderedDict()
    for v in visitors:
        people[v.get("student_id")] = {
            "student_id": v.get("student_id"),
            "name": _pretty_name(v.get("normalized_name")),
            "college": v.get("college") or "-",
            "entries": 0,
            "last": None,
        }

    for r in rows:
        if r.get("action") != "Time In":
            continue
        ts = _parse_ts(r.get("timestamp"))
        if ts is None or (clip and not (clip[0] <= ts < clip[1])):
            continue
        sid = r.get("student_id")
        person = people.get(sid)
        if person is None:
            person = people[sid] = {
                "student_id": sid,
                "name": _pretty_name(r.get("normalized_name")),
                "college": r.get("college") or "-",
                "entries": 0,
                "last": None,
            }
        person["entries"] += 1
        if person["last"] is None or ts > person["last"]:
            person["last"] = ts

    ordered = sorted(people.values(), key=lambda p: (-p["entries"], str(p["name"]).lower()))
    return jsonify({
        "period": period_label,
        "total_entries": sum(p["entries"] for p in ordered),
        "visitors": [
            {
                "student_id": p["student_id"],
                "name": p["name"],
                "college": p["college"],
                "entries": p["entries"],
                "last_entry": p["last"].strftime("%b %d, %Y %I:%M %p") if p["last"] else None,
            }
            for p in ordered
        ],
    })

# ==================== PDF export (chart) ====================

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

_TS_FORMATS = ("%Y-%m-%d %I:%M:%S %p", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %I:%M %p")

def _parse_ts(value):
    text = str(value or "").strip()
    for fmt in _TS_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None

def _build_stay_sessions(rows, clip=None):
    ph_now = datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)
    events = OrderedDict()
    for r in rows:
        ts = _parse_ts(r.get("timestamp"))
        if ts is None or r.get("action") not in ("Time In", "Time Out"):
            continue
        events.setdefault(r.get("student_id"), []).append((ts, r.get("action"), r))

    sessions = []
    orphans = 0

    def add(row, start, end):
        is_open = end is None
        if is_open:
            day_end = datetime.combine(start.date(), datetime.min.time()) + timedelta(days=1)
            end = min(ph_now, day_end)
            if end <= start:
                end = start + timedelta(minutes=1)
        if clip:
            if end < clip[0] or start >= clip[1]:
                return
            start, end = max(start, clip[0]), min(end, clip[1])
        sessions.append({
            "sid": row.get("student_id"), "name": row.get("normalized_name"),
            "college": row.get("college"), "start": start, "end": end, "open": is_open,
        })

    for sid, items in events.items():
        pending = None
        for ts, action, row in items:
            if action == "Time In":
                if pending:
                    add(pending[1], pending[0], None)
                pending = (ts, row)
            elif pending:
                add(pending[1], pending[0], ts)
                pending = None
            elif not clip or (clip[0] <= ts < clip[1]):
                orphans += 1
        if pending:
            add(pending[1], pending[0], None)

    sessions.sort(key=lambda s: (s["start"], s["end"]))
    return sessions, orphans

def _split_by_day(sess):
    segments = []
    day = datetime.combine(sess["start"].date(), datetime.min.time())
    while True:
        next_day = day + timedelta(days=1)
        seg_start, seg_end = max(sess["start"], day), min(sess["end"], next_day)
        if seg_end > seg_start or sess["start"] == sess["end"]:
            segments.append((
                day.date(),
                (seg_start - day).total_seconds() / 60,
                (seg_end - day).total_seconds() / 60,
                sess["open"],
            ))
        if sess["end"] <= next_day:
            break
        day = next_day
    return segments

def _fmt_minutes(minutes):
    minutes = int(round(minutes))
    if minutes < 1:
        return "<1m"
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours}h {mins}m"
    return f"{hours}h" if hours else f"{mins}m"

def _fmt_hour(hour):
    hour = int(hour) % 24
    return f"{hour % 12 or 12} {'AM' if hour < 12 else 'PM'}"

def _build_export_pdf(mode, sessions, period_label, student=None, orphans=0):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.platypus import Flowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer

    green = colors.HexColor("#047857")
    amber = colors.HexColor("#d97706")
    dark = colors.HexColor("#064e3b")
    zebra = colors.HexColor("#f1f7f3")
    grid = colors.HexColor("#d1d5db")
    grid_minor = colors.HexColor("#e5e7eb")
    slate = colors.HexColor("#475569")

    page = landscape(A4)
    margin = 15 * mm
    content_w = page[0] - 2 * margin

    base = getSampleStyleSheet()
    title_style = ParagraphStyle("t", parent=base["Title"], fontName="Helvetica-Bold", fontSize=16, textColor=dark, alignment=0, spaceAfter=2)
    sub_style = ParagraphStyle("s", parent=base["Normal"], fontName="Helvetica", fontSize=8.5, textColor=slate, leading=12)
    note_style = ParagraphStyle("n", parent=sub_style, fontSize=7.5, textColor=colors.HexColor("#64748b"), leading=10)
    day_style = ParagraphStyle("d", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=9.5, textColor=dark, spaceAfter=2)

    days = OrderedDict()
    for s in sessions:
        for day, a, b, is_open in _split_by_day(s):
            bucket = days.setdefault(day, OrderedDict())
            key = "stay" if mode == "student" else s["sid"]
            row = bucket.get(key)
            if row is None:
                label = day.strftime("%Y-%m-%d (%a)") if mode == "student" else _pretty_name(s["name"])
                row = bucket[key] = {"label": label, "sub": "" if mode == "student" else (s["college"] or ""),
                                     "segs": [], "total": 0.0, "first": a}
            row["segs"].append((a, b, is_open))
            row["total"] += b - a
            row["first"] = min(row["first"], a)
    ordered_days = sorted(days)

    all_segs = [seg for bucket in days.values() for row in bucket.values() for seg in row["segs"]]
    lo = int(min(a for a, _, _ in all_segs) // 60)
    hi = int(-(-max(b for _, b, _ in all_segs) // 60))
    need = 6 - (hi - lo)
    if need > 0:
        lo = max(0, lo - need // 2)
        hi = min(24, hi + need - need // 2)
        if hi - lo < 6:
            lo = max(0, hi - 6)
        if hi - lo < 6:
            hi = lo + 6
    span_h = hi - lo
    tick_step = 1 if span_h <= 8 else (2 if span_h <= 14 else 3)

    ROW_H, HEAD_H, BAR_H = 6.5 * mm, 6.5 * mm, 3.5 * mm
    LABEL_W, TOTAL_W = 62 * mm, 22 * mm
    ROWS_PER_CHUNK = 16

    class GanttChart(Flowable):
        def __init__(self, rows, label_head, show_sub):
            super().__init__()
            self.rows, self.label_head, self.show_sub = rows, label_head, show_sub
            self.width = content_w
            self.height = HEAD_H + len(rows) * ROW_H

        def wrap(self, avail_w, avail_h):
            return self.width, self.height

        def _x(self, minute):
            plot_w = self.width - LABEL_W - TOTAL_W
            return LABEL_W + (minute / 60.0 - lo) / span_h * plot_w

        def _fit(self, text, font, size, max_w):
            if stringWidth(text, font, size) <= max_w:
                return text
            while text and stringWidth(text + "...", font, size) > max_w:
                text = text[:-1]
            return text + "..."

        def draw(self):
            c = self.canv
            w, h = self.width, self.height
            plot_x, plot_end = LABEL_W, w - TOTAL_W

            c.setFillColor(green)
            c.rect(0, h - HEAD_H, w, HEAD_H, stroke=0, fill=1)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 7.5)
            c.drawString(3 * mm, h - HEAD_H / 2 - 2.5, self.label_head)
            c.drawCentredString(plot_end + TOTAL_W / 2, h - HEAD_H / 2 - 2.5, "Total")

            for i in range(len(self.rows)):
                if i % 2 == 1:
                    c.setFillColor(zebra)
                    c.rect(0, h - HEAD_H - (i + 1) * ROW_H, w, ROW_H, stroke=0, fill=1)

            for hour in range(lo, hi + 1):
                x = self._x(hour * 60)
                major = (hour - lo) % tick_step == 0
                c.setStrokeColor(grid if major else grid_minor)
                c.setLineWidth(0.5 if major else 0.25)
                c.line(x, 0, x, h - HEAD_H)
                if major:
                    c.setFillColor(colors.white)
                    c.setFont("Helvetica", 6.5)
                    c.drawCentredString(x, h - HEAD_H / 2 - 2.5, _fmt_hour(hour))

            for i, row in enumerate(self.rows):
                y_bot = h - HEAD_H - (i + 1) * ROW_H
                y_mid = y_bot + ROW_H / 2
                sub_w = stringWidth(row["sub"], "Helvetica", 6) + 3 * mm if (self.show_sub and row["sub"]) else 0
                c.setFillColor(colors.HexColor("#0f172a"))
                c.setFont("Helvetica-Bold" if not self.show_sub else "Helvetica", 7.5)
                c.drawString(3 * mm, y_mid - 2.5, self._fit(row["label"], "Helvetica", 7.5, LABEL_W - 6 * mm - sub_w))
                if sub_w:
                    c.setFillColor(colors.HexColor("#64748b"))
                    c.setFont("Helvetica", 6)
                    c.drawRightString(LABEL_W - 2 * mm, y_mid - 2, row["sub"])

                for a, b, is_open in row["segs"]:
                    x1, x2 = self._x(a), self._x(b)
                    bar_w = max(x2 - x1, 1.2 * mm)
                    c.setFillColor(amber if is_open else green)
                    c.roundRect(x1, y_mid - BAR_H / 2, bar_w, BAR_H, 1 * mm, stroke=0, fill=1)
                    text = _fmt_minutes(b - a) + ("*" if is_open else "")
                    if stringWidth(text, "Helvetica-Bold", 6) + 2 * mm < bar_w:
                        c.setFillColor(colors.white)
                        c.setFont("Helvetica-Bold", 6)
                        c.drawCentredString(x1 + bar_w / 2, y_mid - 2, text)

                c.setFillColor(dark)
                c.setFont("Helvetica-Bold", 7.5)
                c.drawCentredString(plot_end + TOTAL_W / 2, y_mid - 2.5, _fmt_minutes(row["total"]))

            c.setStrokeColor(grid)
            c.setLineWidth(0.6)
            c.rect(0, 0, w, h, stroke=1, fill=0)
            c.line(plot_x, 0, plot_x, h - HEAD_H)
            c.line(plot_end, 0, plot_end, h - HEAD_H)

    class Legend(Flowable):
        def wrap(self, avail_w, avail_h):
            return avail_w, 4 * mm

        def draw(self):
            c = self.canv
            x = 0
            for color, text in ((green, "Completed Stay"), (amber, "Open Stay*")):
                c.setFillColor(color)
                c.roundRect(x, 0.6 * mm, 6 * mm, 2.5 * mm, 0.6 * mm, stroke=0, fill=1)
                c.setFillColor(slate)
                c.setFont("Helvetica", 7.5)
                c.drawString(x + 7.5 * mm, 0.9 * mm, text)
                x += 7.5 * mm + stringWidth(text, "Helvetica", 7.5) + 6 * mm

    durations = [(s["end"] - s["start"]).total_seconds() / 60 for s in sessions]
    closed = [d for s, d in zip(sessions, durations) if not s["open"]]
    open_count = sum(1 for s in sessions if s["open"])
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    story = []
    if mode == "student":
        story.append(Paragraph("Visitor Activity Log", title_style))
        story.append(Paragraph(f"<b>{_esc(_pretty_name(student.get('normalized_name')))}</b> &nbsp;|&nbsp; ID: {_esc(student.get('student_id'))} &nbsp;|&nbsp; {_esc(student.get('college'))}", sub_style))
    else:
        story.append(Paragraph("GuardGate Attendance", title_style))
    
    story.append(Paragraph(f"Period: {_esc(period_label)} &nbsp;|&nbsp; Generated: {generated}", sub_style))
    story.append(Spacer(1, 2 * mm))

    stats = []
    if mode != "student":
        stats.append(f"Visitors: <b>{len({s['sid'] for s in sessions})}</b>")
    stats.append(f"Stays: <b>{len(sessions)}</b>")
    stats.append(f"Days: <b>{len(ordered_days)}</b>")
    stats.append(f"Total Time: <b>{_fmt_minutes(sum(durations))}</b>")
    if closed:
        stats.append(f"Avg Stay: <b>{_fmt_minutes(sum(closed) / len(closed))}</b>")
    story.append(Paragraph(" &nbsp;|&nbsp; ".join(stats), sub_style))
    story.append(Spacer(1, 1.5 * mm))
    story.append(Legend())

    notes = []
    if open_count:
        notes.append(f"* {open_count} open stay(s) without Time Out.")
    if orphans:
        notes.append(f"{orphans} unrecorded exit(s).")
    if notes:
        story.append(Paragraph(" ".join(notes), note_style))
        story.append(Spacer(1, 2.5 * mm))

    def add_chart(heading, rows, label_head, show_sub):
        for i in range(0, len(rows), ROWS_PER_CHUNK):
            text = heading if i == 0 else f"{heading} (cont.)"
            story.append(KeepTogether([
                Paragraph(_esc(text), day_style),
                GanttChart(rows[i:i + ROWS_PER_CHUNK], label_head, show_sub),
                Spacer(1, 4 * mm),
            ]))

    if mode == "student":
        rows = [row for day in ordered_days for row in days[day].values()]
        add_chart("Daily Timeline", rows, "Date", False)
    else:
        for day in ordered_days:
            rows = sorted(days[day].values(), key=lambda r: (r["first"], r["label"].lower()))
            count = len(rows)
            add_chart(f"{day.strftime('%A, %d %b %Y')} ({count} visitors)", rows, "Visitor", True)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(doc.leftMargin, 6 * mm, "Guard Dashboard")
        canvas.drawRightString(page[0] - doc.rightMargin, 6 * mm, f"Page {doc.page}")
        canvas.restoreState()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=page, leftMargin=margin, rightMargin=margin, topMargin=12 * mm, bottomMargin=12 * mm,
                            title="GuardGate Visit Duration", author="GuardGate")
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
        from reportlab.lib.pagesizes import A4  # noqa: F401
    except ImportError:
        return jsonify({"message": "PDF export needs the reportlab package. Run: pip install reportlab"}), 500

    clip = None
    fetch_start, fetch_end = start, end
    if start and end:
        fmt = "%Y-%m-%d %H:%M:%S"
        clip = (datetime.strptime(start, fmt), datetime.strptime(end, fmt))
        fetch_start = (clip[0] - timedelta(days=1)).strftime(fmt)
        fetch_end = (clip[1] + timedelta(days=1)).strftime(fmt)

    try:
        rows = _fetch_logs_for_export(fetch_start, fetch_end, student_id if mode == 'student' else None)
        sessions, orphans = _build_stay_sessions(rows, clip)
        if not sessions:
            if mode == 'student':
                who = _pretty_name(student.get('normalized_name'))
                where = "on record" if period_label == "All dates" else f"for {period_label}"
                return jsonify({"message": f"No attendance logs found for {who} {where}. Nothing to export."}), 404
            return jsonify({"message": f"No attendance logs found for {period_label}. Nothing to export."}), 404
        pdf = _build_export_pdf(mode, sessions, period_label, student, orphans)
    except Exception:
        logging.exception("Failed to build PDF export")
        return jsonify({"message": "Failed to generate the PDF report."}), 500

    if mode == 'student':
        safe_id = re.sub(r'[^A-Za-z0-9_-]', '_', student_id)
        filename = f"guardgate_{safe_id}.pdf"
    elif from_month == to_month:
        filename = f"guardgate_{from_month}.pdf"
    else:
        filename = f"guardgate_{from_month}_to_{to_month}.pdf"

    return send_file(pdf, mimetype='application/pdf', as_attachment=True, download_name=filename)


@guard_bp.route('/api/students/summary')
def student_summary():
    student_id = request.args.get('student_id', '').strip()
    if not student_id:
        return jsonify({"message": "Choose a visitor."}), 400

    try:
        found = supabase.table("visitors").select("*").eq("student_id", student_id).execute().data
        if not found:
            return jsonify({"message": "Visitor not found."}), 404
        visitor = found[0]
        rows = _fetch_logs_for_export(None, None, student_id)
        sessions, orphans = _build_stay_sessions(rows)
    except Exception:
        logging.exception("Failed to build visitor summary")
        return jsonify({"message": "Failed to load the visitor summary."}), 500

    events = []
    for r in rows:
        ts = _parse_ts(r.get("timestamp"))
        if ts is not None and r.get("action") in ("Time In", "Time Out"):
            events.append((ts, r.get("action")))
    events.sort(key=lambda e: e[0])

    entries = sum(1 for _, action in events if action == "Time In")
    durations = [(s["end"] - s["start"]).total_seconds() / 60 for s in sessions]
    closed = [d for s, d in zip(sessions, durations) if not s["open"]]
    days = {seg[0] for s in sessions for seg in _split_by_day(s)}
    stamp = "%b %d, %Y %I:%M %p"

    recent = []
    for s in reversed(sessions[-5:]):
        recent.append({
            "date": s["start"].strftime("%b %d, %Y"),
            "time_in": s["start"].strftime("%I:%M %p"),
            "time_out": "-" if s["open"] else s["end"].strftime("%I:%M %p"),
            "duration": _fmt_minutes((s["end"] - s["start"]).total_seconds() / 60),
            "open": s["open"],
        })

    return jsonify({
        "student_id": visitor.get("student_id"),
        "name": _pretty_name(visitor.get("normalized_name")),
        "college": visitor.get("college"),
        "course_year": visitor.get("course_year"),
        "entries": entries,
        "days": len(days),
        "total_time": _fmt_minutes(sum(durations)) if durations else "-",
        "average_stay": _fmt_minutes(sum(closed) / len(closed)) if closed else "-",
        "longest_stay": _fmt_minutes(max(closed)) if closed else "-",
        "open_stays": sum(1 for s in sessions if s["open"]),
        "unrecorded_exits": orphans,
        "first_visit": events[0][0].strftime(stamp) if events else None,
        "last_visit": events[-1][0].strftime(stamp) if events else None,
        "status": ("Inside" if events[-1][1] == "Time In" else "Outside") if events else None,
        "recent": recent,
    })