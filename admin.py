import os
import sys
import logging
from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template_string, request, jsonify, session, redirect, url_for
from supabase import create_client, Client

admin_bp = Blueprint('admin_bp', __name__)

SUPABASE_URL = "https://qciehqzajzaejhsjzrdm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFjaWVocXphanphZWpoc2p6cmRtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODkwODQwNDksImV4cCI6MjEwNDY2MDA0OX0.0An1BSRjssOI7SliI1lC3jkMo14XVHbUnfXFt015Uyo"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

ADMIN_DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dormitory Admin Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Plus Jakarta Sans', sans-serif; background: linear-gradient(135deg, #f2f7f3 0%, #eaf3ed 50%, #f4f8f5 100%); }
    </style>
    <script>
        function toggleNavMenu(event) {
            event.stopPropagation();
            const panel = document.getElementById('nav-menu-panel');
            const open = panel.classList.toggle('hidden') === false;
            document.getElementById('nav-menu-btn').setAttribute('aria-expanded', String(open));
        }

        function closeNavMenu() {
            const panel = document.getElementById('nav-menu-panel');
            if (panel) {
                panel.classList.add('hidden');
                document.getElementById('nav-menu-btn').setAttribute('aria-expanded', 'false');
            }
        }

        document.addEventListener('click', (e) => {
            if (!e.target.closest('#nav-menu-panel') && !e.target.closest('#nav-menu-btn')) closeNavMenu();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeNavMenu();
        });
    </script>
</head>
<body class="text-slate-800 p-6 min-h-screen">
    <div class="max-w-6xl mx-auto">
        <header class="flex justify-between items-center mb-6 bg-white p-5 rounded-2xl shadow-sm border border-emerald-900/10">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-xl bg-emerald-700 text-white flex items-center justify-center shadow-md">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>
                </div>
                <div>
                    <h1 class="text-xl font-bold text-emerald-950">Dormitory Admin Dashboard</h1>
                    <p class="text-xs text-slate-500">Real-time occupancy and visitor management</p>
                </div>
            </div>

            <div class="relative shrink-0 flex items-center gap-4">
                <div id="live-clock" class="text-right leading-tight">
                    <p data-time class="text-sm font-bold text-emerald-950 tabular-nums"></p>
                    <p data-date class="text-[11px] font-medium text-slate-500"></p>
                </div>
                <button type="button" id="nav-menu-btn" onclick="toggleNavMenu(event)" aria-haspopup="true" aria-expanded="false" aria-controls="nav-menu-panel" aria-label="Open menu" class="w-10 h-10 rounded-xl bg-emerald-800 hover:bg-emerald-900 text-white flex items-center justify-center shadow-sm border border-emerald-900/20 transition focus:outline-none focus:ring-4 focus:ring-emerald-500/20">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path></svg>
                </button>
                <div id="nav-menu-panel" role="menu" class="hidden absolute right-0 top-12 mt-2 w-56 bg-white rounded-xl shadow-xl shadow-slate-900/10 border border-slate-200 py-1.5 z-40">
                    <p class="px-4 pt-1.5 pb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">Navigate</p>
                    <a href="/guard" role="menuitem" class="flex items-center gap-2.5 px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-emerald-50 hover:text-emerald-900 transition-colors">
                        <svg class="w-4 h-4 text-emerald-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg>
                        Guard Station
                    </a>
                    <a href="/scanner" role="menuitem" class="flex items-center gap-2.5 px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-emerald-50 hover:text-emerald-900 transition-colors">
                        <svg class="w-4 h-4 text-emerald-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                        Student Scanner
                    </a>
                    <div class="my-1.5 border-t border-slate-100"></div>
                    <a href="/admin-logout" role="menuitem" class="flex items-center gap-2.5 px-4 py-2.5 text-xs font-semibold text-rose-600 hover:bg-rose-50 transition-colors">
                        <svg class="w-4 h-4 text-rose-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path></svg>
                        Logout
                    </a>
                </div>
            </div>
        </header>

        <div class="bg-white p-6 rounded-2xl shadow-sm border border-emerald-900/10 mb-6">
            <div class="mb-4">
                <h2 class="text-sm font-bold text-emerald-950 flex items-center gap-2">
                    <span class="w-2.5 h-2.5 rounded-full bg-emerald-600 animate-pulse"></span>
                    Real-time: Dormitory Visitors
                </h2>
                <p id="occupancy-sub" class="text-xs text-slate-500 mt-1"></p>
            </div>
            <div class="flex flex-col sm:flex-row sm:items-end gap-3 mb-5 pb-5 border-b border-slate-100">
                <div class="sm:w-60 shrink-0">
                    <label for="occupancy-filter" class="block text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-1.5">View</label>
                    <div class="relative">
                        <select id="occupancy-filter" autocomplete="off" onchange="setOccupancyView(this.value)" class="w-full appearance-none bg-white border border-slate-300 rounded-xl pl-3.5 pr-9 py-2 text-xs font-medium text-slate-800 shadow-sm cursor-pointer outline-none transition hover:border-slate-400 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600">
                            <option value="inside">Inside</option>
                            <option value="out">Out</option>
                            <option value="overstay">Overstay (8 PM to 6 AM)</option>
                        </select>
                        <svg class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                    </div>
                </div>
                <div class="sm:w-52 shrink-0">
                    <label for="category-filter" class="block text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-1.5">Category</label>
                    <div class="relative">
                        <select id="category-filter" autocomplete="off" onchange="filterCategory(this.value)" class="w-full appearance-none bg-white border border-slate-300 rounded-xl pl-3.5 pr-9 py-2 text-xs font-medium text-slate-800 shadow-sm cursor-pointer outline-none transition hover:border-slate-400 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600">
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
                        <input type="text" id="search-input" oninput="renderOccupancy()" placeholder="Search name" autocomplete="off" class="w-full bg-white border border-slate-300 rounded-xl pl-9 pr-3.5 py-2 text-xs text-slate-800 shadow-sm outline-none transition hover:border-slate-400 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600">
                    </div>
                </div>
            </div>
            <ul id="occupancy-list" class="max-h-96 overflow-y-auto grid grid-cols-1 xl:grid-cols-2 gap-2"></ul>
        </div>

        <div class="bg-white p-6 rounded-2xl shadow-sm border border-emerald-900/10">
            <h2 class="text-sm font-bold text-emerald-950 mb-4">Manage Visitors</h2>
            <div class="overflow-x-auto">
                <table class="w-full text-left text-xs">
                    <thead>
                        <tr class="border-b border-slate-100 text-slate-400 uppercase font-semibold">
                            <th class="p-3">ID Number</th>
                            <th class="p-3">Full Name</th>
                            <th class="p-3">Category / College</th>
                            <th class="p-3">Course / Details</th>
                            <th class="p-3">Actions</th>
                        </tr>
                    </thead>
                    <tbody id="visitors-tbody"></tbody>
                </table>
            </div>
        </div>
    </div>

    <div id="delete-modal" class="hidden fixed inset-0 z-[60] flex items-center justify-center p-4 bg-slate-950/50 backdrop-blur-sm" role="alertdialog" aria-modal="true" aria-labelledby="delete-modal-title" aria-describedby="delete-modal-message" onmousedown="if (event.target === this) closeDeleteModal()">
        <div class="bg-white rounded-2xl shadow-2xl shadow-slate-900/20 w-full max-w-sm overflow-hidden border border-slate-200">
            <div class="px-6 pt-6 pb-5 flex items-start gap-3.5">
                <div class="w-10 h-10 rounded-xl bg-rose-50 text-rose-600 border border-rose-200 flex items-center justify-center shrink-0">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                </div>
                <div class="min-w-0">
                    <h3 id="delete-modal-title" class="text-sm font-bold text-slate-900">Delete this visitor?</h3>
                    <p id="delete-modal-message" class="text-xs text-slate-500 mt-1.5 leading-relaxed">
                        <span id="delete-modal-name" class="font-semibold text-slate-700 break-words"></span> will be permanently removed, including their logs and stored face image. This cannot be undone.
                    </p>
                </div>
            </div>
            <div class="px-6 py-4 bg-slate-50/70 border-t border-slate-100 flex items-center justify-end gap-3">
                <button type="button" id="delete-cancel-btn" onclick="closeDeleteModal()" class="px-4 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-300 rounded-xl hover:bg-slate-50 transition shadow-sm">Cancel</button>
                <button type="button" id="delete-ok-btn" onclick="confirmDeleteVisitor()" class="px-4 py-2 text-xs font-semibold text-white bg-rose-600 rounded-xl hover:bg-rose-700 focus:ring-4 focus:ring-rose-500/20 transition shadow-sm disabled:opacity-50 disabled:cursor-not-allowed">Delete</button>
            </div>
        </div>
    </div>

    <div id="toast" class="hidden"></div>

    <script>
        function loadDashboardData() {
            fetch('/api/admin/stats')
                .then(r => r.json())
                .then(data => {
                    const tbody = document.getElementById('visitors-tbody');
                    tbody.innerHTML = '';
                    if (data.visitors.length === 0) {
                        tbody.innerHTML = `<tr><td colspan="5" class="p-6 text-center text-slate-400">No visitors found.</td></tr>`;
                        return;
                    }
                    data.visitors.forEach(v => {
                        tbody.innerHTML += `
                            <tr class="border-b border-slate-100 hover:bg-emerald-50/30 transition-colors">
                                <td class="p-3 font-semibold text-slate-900">${v.student_id}</td>
                                <td class="p-3 font-medium">${v.normalized_name}</td>
                                <td class="p-3"><span class="bg-emerald-50 text-emerald-800 border border-emerald-200 px-2 py-0.5 rounded-full font-semibold">${v.college}</span></td>
                                <td class="p-3 text-slate-600">${v.course_year || '-'}</td>
                                <td class="p-3 flex gap-2">
                                    <button type="button" data-id="${escapeHtml(v.student_id)}" data-name="${escapeHtml(v.normalized_name)}" onclick="requestDeleteVisitor(this)" class="bg-rose-50 text-rose-700 border border-rose-200 px-3 py-1 rounded-lg font-medium hover:bg-rose-100 transition">Delete</button>
                                </td>
                            </tr>`;
                    });
                }).catch(() => {});
        }

        let occupancyData = { inside: [], out: [], overstay: [], overstay_active: false, cutoff: '', now: '' };
        let occupancyView = 'inside';
        let currentCategory = 'ALL';

        const OCCUPANCY_LABELS = { inside: 'Inside', out: 'Out', overstay: 'Overstay (8 PM to 6 AM)' };
        const OCCUPANCY_SUBS = {
            inside: 'Visitors currently checked in to the dormitory.',
            out: 'Visitors whose latest record is a Time Out.',
            overstay: 'Visitors still inside the dormitory during the night curfew period, 8 PM to 6 AM.'
        };

        function setOccupancyView(view) {
            occupancyView = view;
            renderOccupancy();
        }

        function filterCategory(code) {
            currentCategory = code;
            renderOccupancy();
        }

        function normalizeSearch(value) {
            return String(value == null ? '' : value).toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
        }

        function applyOccupancyFilters(list) {
            const q = normalizeSearch(document.getElementById('search-input').value);
            return list.filter(v => {
                if (currentCategory !== 'ALL' && v.college !== currentCategory) return false;
                if (!q) return true;
                return normalizeSearch(v.name + ' ' + v.student_id + ' ' + (v.course_year || '')).includes(q);
            });
        }

        function occupancyEmptyMessage(view) {
            const q = document.getElementById('search-input').value.trim();
            if (q || currentCategory !== 'ALL') return 'No visitors match the current filters.';
            if (view === 'inside') return 'No visitors are currently inside.';
            if (view === 'out') return 'No visitors have checked out yet.';
            return occupancyData.overstay_active
                ? 'No visitors are overstaying.'
                : 'Overstay monitoring runs from 8 PM to 6 AM and is not active right now.';
        }

        function occupancyItem(v, view) {
            const name = escapeHtml(v.name);
            const id = escapeHtml(v.student_id);
            const details = escapeHtml(v.college) + ' | ' + escapeHtml(v.course_year || '-');
            let card = 'border-slate-200 bg-white';
            let badge = 'bg-emerald-100 text-emerald-800 border-emerald-200';
            let badgeText = 'Time In';
            let line = '<p class="text-[11px] text-slate-500 truncate">' + details + ' | In since ' + escapeHtml(v.time) + '</p>';

            if (view === 'out') {
                badge = 'bg-rose-100 text-rose-800 border-rose-200';
                badgeText = 'Time Out';
                line = '<p class="text-[11px] text-slate-500 truncate">' + details + ' | Out at ' + escapeHtml(v.time) + '</p>';
            } else if (view === 'overstay') {
                card = 'border-rose-200 bg-rose-50/60';
                badge = 'bg-rose-100 text-rose-800 border-rose-200';
                badgeText = 'Overstay';
                const warn = v.stale
                    ? 'No Time Out since ' + escapeHtml(v.time)
                    : escapeHtml(v.over_label) + ' past ' + escapeHtml(occupancyData.cutoff);
                line = '<p class="text-[11px] text-slate-500 truncate">' + details + ' | In since ' + escapeHtml(v.time) + '</p>' +
                    '<p class="text-[11px] font-bold text-rose-700 mt-0.5">' + warn + '</p>';
            }

            return '<li class="flex items-center justify-between gap-3 rounded-xl border px-3.5 py-2.5 ' + card + '">' +
                '<div class="min-w-0">' +
                '<p class="text-xs font-bold text-slate-900 truncate">' + name + ' <span class="text-slate-400 font-medium">(' + id + ')</span></p>' +
                line +
                '</div>' +
                '<span class="shrink-0 px-2 py-0.5 rounded-md font-semibold text-[11px] border ' + badge + '">' + badgeText + '</span>' +
                '</li>';
        }

        function renderOccupancy() {
            const select = document.getElementById('occupancy-filter');
            Array.from(select.options).forEach(opt => {
                opt.textContent = OCCUPANCY_LABELS[opt.value] + ' (' + applyOccupancyFilters(occupancyData[opt.value] || []).length + ')';
            });
            select.value = occupancyView;
            document.getElementById('occupancy-sub').innerText = OCCUPANCY_SUBS[occupancyView];

            const list = applyOccupancyFilters(occupancyData[occupancyView] || []);
            const container = document.getElementById('occupancy-list');
            if (list.length === 0) {
                container.innerHTML = '<li class="xl:col-span-2 p-6 text-center text-slate-400 text-xs">' + occupancyEmptyMessage(occupancyView) + '</li>';
                return;
            }
            container.innerHTML = list.map(v => occupancyItem(v, occupancyView)).join('');
        }

        function loadOccupancy() {
            fetch('/api/admin/occupancy')
                .then(r => r.json())
                .then(data => {
                    if (!data.inside) return;
                    occupancyData = data;
                    renderOccupancy();
                }).catch(() => {});
        }

        let pendingDeleteId = null;

        function escapeHtml(value) {
            return String(value == null ? '' : value)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        function showToast(message, isError) {
            const toast = document.getElementById('toast');
            toast.innerText = message;
            toast.className = 'fixed bottom-6 right-6 z-[70] px-4 py-3 rounded-xl shadow-lg text-xs font-semibold border ' +
                (isError ? 'bg-rose-50 text-rose-700 border-rose-200' : 'bg-emerald-50 text-emerald-800 border-emerald-200');
            toast.classList.remove('hidden');
            clearTimeout(showToast.timer);
            showToast.timer = setTimeout(() => toast.classList.add('hidden'), 3500);
        }

        function requestDeleteVisitor(btn) {
            pendingDeleteId = btn.dataset.id;
            document.getElementById('delete-modal-name').innerText = btn.dataset.name || btn.dataset.id;
            const ok = document.getElementById('delete-ok-btn');
            ok.disabled = false;
            ok.innerText = 'Delete';
            document.getElementById('delete-modal').classList.remove('hidden');
            setTimeout(() => document.getElementById('delete-cancel-btn').focus(), 50);
        }

        function closeDeleteModal() {
            document.getElementById('delete-modal').classList.add('hidden');
            pendingDeleteId = null;
        }

        function confirmDeleteVisitor() {
            if (!pendingDeleteId) return;
            const id = pendingDeleteId;
            const ok = document.getElementById('delete-ok-btn');
            ok.disabled = true;
            ok.innerText = 'Deleting...';
            fetch('/api/admin/delete-visitor', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ student_id: id })
            })
            .then(r => r.json().then(res => ({ ok: r.ok, res })))
            .then(({ ok, res }) => {
                showToast(res.message, !ok);
                loadDashboardData();
            })
            .catch(() => showToast('Failed to delete visitor. Please try again.', true))
            .finally(closeDeleteModal);
        }

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeDeleteModal();
        });

        function tickClock() {
            const el = document.getElementById('live-clock');
            if (!el) return;
            const d = new Date();
            const opt = { timeZone: 'Asia/Manila' };
            el.querySelector('[data-time]').textContent = d.toLocaleTimeString('en-PH', { ...opt, hour: 'numeric', minute: '2-digit', second: '2-digit' });
            el.querySelector('[data-date]').textContent = d.toLocaleDateString('en-PH', { ...opt, weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
        }
        document.addEventListener('DOMContentLoaded', () => { tickClock(); setInterval(tickClock, 1000); });

        window.onload = () => {
            loadOccupancy();
            loadDashboardData();
            setInterval(loadOccupancy, 5000);
            setInterval(loadDashboardData, 5000);
        };
    </script>
</body>
</html>
"""

ADMIN_LOGIN_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Dashboard Login</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>body { font-family: 'Plus Jakarta Sans', sans-serif; background: linear-gradient(135deg, #f2f7f3 0%, #eaf3ed 50%, #f4f8f5 100%); }</style>
</head>
<body class="flex items-center justify-center h-screen p-4">
    <div class="bg-white p-8 rounded-2xl shadow-lg w-full max-w-sm border border-emerald-900/10">
        <a href="/login" class="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-800 hover:text-emerald-900 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 px-3 py-1.5 rounded-lg transition-colors mb-5"><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M15 19l-7-7 7-7"></path></svg>Back</a>
        <div class="mx-auto w-12 h-12 rounded-xl bg-emerald-700 text-white flex items-center justify-center shadow-md mb-4">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg>
        </div>
        <h2 class="text-xl font-bold text-emerald-950 text-center mb-1">Admin Dashboard</h2>
        <p class="text-xs text-slate-500 text-center mb-6">Sign in to manage dormitory records</p>
        {% if error %}<p class="bg-rose-50 border border-rose-200 text-rose-700 text-xs px-3 py-2 rounded-lg mb-4 text-center font-medium">{{ error }}</p>{% endif %}
        <form method="POST" class="space-y-4">
            <div>
                <label class="block text-xs font-semibold text-slate-700 mb-1">Username</label>
                <input type="text" name="username" required class="w-full border border-slate-300 rounded-xl px-3.5 py-2.5 text-sm outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600">
            </div>
            <div>
                <label class="block text-xs font-semibold text-slate-700 mb-1">Password</label>
                <input type="password" name="password" required class="w-full border border-slate-300 rounded-xl px-3.5 py-2.5 text-sm outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-600">
            </div>
            <button type="submit" class="w-full bg-emerald-800 hover:bg-emerald-900 text-white text-sm font-semibold py-2.5 rounded-xl shadow-sm transition">Login</button>
        </form>
    </div>
</body>
</html>
"""

@admin_bp.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if session.get('is_admin'):
        return redirect(url_for('admin_bp.admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if username == 'mmsu@admin123' and password == 'adminMmsu':
            session['is_admin'] = True
            return redirect(url_for('admin_bp.admin_dashboard'))
        else:
            return render_template_string(ADMIN_LOGIN_TEMPLATE, error='Invalid credentials')
            
    return render_template_string(ADMIN_LOGIN_TEMPLATE)

@admin_bp.route('/admin-logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('admin_bp.admin_login'))

@admin_bp.route('/admin-dashboard')
def admin_dashboard():
    if not session.get('is_admin'):
        return redirect(url_for('admin_bp.admin_login'))
    return render_template_string(ADMIN_DASHBOARD_TEMPLATE)

@admin_bp.route('/api/admin/stats')
def admin_stats():
    if not session.get('is_admin'):
        return jsonify({"error": "Unauthorized"}), 401

    visitors = supabase.table("visitors").select("*").execute().data or []
    return jsonify({"visitors": visitors})

CURFEW_HOUR = 20
ALERT_END_HOUR = 6
CURFEW_LOOKBACK_DAYS = 7
PH_TZ = timezone(timedelta(hours=8))
_TS_FORMATS = ("%Y-%m-%d %I:%M:%S %p", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %I:%M %p")

def _parse_ts(value):
    text = str(value or "").strip()
    for fmt in _TS_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None

def _pretty_name(raw):
    parts = [p.strip() for p in (raw or "").split(",")]
    parts = [p for p in parts if p and p.upper() != "N/A"]
    if len(parts) <= 1:
        return parts[0] if parts else (raw or "-")
    return f"{parts[0]}, {' '.join(parts[1:])}"

def _over_label(minutes):
    minutes = max(0, int(minutes))
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours}h {mins}m"
    return f"{hours}h" if hours else f"{mins}m"

def _curfew_start(now):
    midnight = datetime.combine(now.date(), datetime.min.time())
    if now.hour >= CURFEW_HOUR:
        return midnight.replace(hour=CURFEW_HOUR)
    if now.hour < ALERT_END_HOUR:
        return (midnight - timedelta(days=1)).replace(hour=CURFEW_HOUR)
    return None

def _latest_actions(visitor_ids):
    latest = {}
    remaining = set(visitor_ids)
    page_size = 1000
    offset = 0
    while remaining:
        batch = (
            supabase.table("logs")
            .select("student_id,action,timestamp")
            .in_("action", ["Time In", "Time Out"])
            .order("id", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
            .data
        ) or []
        for row in batch:
            sid = row.get("student_id")
            if sid in remaining:
                latest[sid] = row
                remaining.discard(sid)
        if len(batch) < page_size:
            break
        offset += page_size
    return latest

@admin_bp.route('/api/admin/occupancy')
def admin_occupancy():
    if not session.get('is_admin'):
        return jsonify({"error": "Unauthorized"}), 401

    now = datetime.now(PH_TZ).replace(tzinfo=None)
    curfew = _curfew_start(now)

    try:
        visitors = supabase.table("visitors").select("*").execute().data or []
        latest = _latest_actions([v["student_id"] for v in visitors])
    except Exception:
        logging.exception("Failed to load visitor occupancy")
        return jsonify({"message": "Failed to load visitor occupancy."}), 500

    def stamp(ts):
        if ts is None:
            return "-"
        if ts.date() == now.date():
            return ts.strftime("%I:%M %p")
        return ts.strftime("%b %d, %I:%M %p")

    inside, out, overstay = [], [], []
    for v in visitors:
        row = latest.get(v["student_id"])
        if not row:
            continue
        ts = _parse_ts(row.get("timestamp"))
        entry = {
            "student_id": v["student_id"],
            "name": _pretty_name(v.get("normalized_name")),
            "college": v.get("college") or "-",
            "course_year": v.get("course_year"),
            "time": stamp(ts),
            "_ts": ts or datetime.min,
        }
        if row.get("action") == "Time Out":
            out.append(entry)
            continue
        inside.append(entry)
        if curfew is None or ts is None or ts > now:
            continue
        if ts < now - timedelta(days=CURFEW_LOOKBACK_DAYS):
            continue
        minutes_over = (now - curfew).total_seconds() / 60
        overstay.append({
            **entry,
            "stale": ts.date() < curfew.date(),
            "minutes_over": int(minutes_over),
            "over_label": _over_label(minutes_over),
        })

    inside.sort(key=lambda e: e["_ts"], reverse=True)
    out.sort(key=lambda e: e["_ts"], reverse=True)
    overstay.sort(key=lambda e: (not e["stale"], -e["minutes_over"], e["name"].lower()))

    for group in (inside, out, overstay):
        for e in group:
            e.pop("_ts", None)

    return jsonify({
        "inside": inside,
        "out": out,
        "overstay": overstay,
        "overstay_active": curfew is not None,
        "cutoff": "8:00 PM",
        "now": now.strftime("%I:%M %p").lstrip("0"),
    })

def _face_file_name(visitor, student_id):
    candidate = ""
    if visitor:
        image_path = (visitor.get("image_path") or "").split("?")[0]
        candidate = os.path.basename(image_path.rstrip("/"))
    if not candidate or candidate in (".", ".."):
        candidate = f"{student_id}.jpg"
    return os.path.basename(candidate)

def _local_face_dir():
    main_module = sys.modules.get("__main__")
    return getattr(main_module, "FACE_DIR", "captured_faces")

def _refresh_recognizer():
    for name in ("__main__", "app"):
        module = sys.modules.get(name)
        loader = getattr(module, "load_recognizer_training", None)
        if callable(loader):
            loader()
            return

@admin_bp.route('/api/admin/delete-visitor', methods=['POST'])
def admin_delete_visitor():
    if not session.get('is_admin'):
        return jsonify({"message": "Unauthorized"}), 401

    data = request.get_json() or {}
    s_id = data.get('student_id')
    if not s_id:
        return jsonify({"message": "Missing student ID"}), 400

    try:
        rows = supabase.table("visitors").select("*").eq("student_id", s_id).execute().data or []
        file_names = {_face_file_name(row, s_id) for row in rows} or {f"{s_id}.jpg"}
        file_names.add(f"{s_id}.jpg")

        supabase.storage.from_("faces").remove(sorted(file_names))

        supabase.table("visitors").delete().eq("student_id", s_id).execute()
        supabase.table("logs").delete().eq("student_id", s_id).execute()
    except Exception as e:
        logging.exception("Failed to delete visitor %s", s_id)
        return jsonify({"message": f"Error: {e}"}), 500

    face_dir = _local_face_dir()
    for name in file_names:
        local_path = os.path.join(face_dir, name)
        try:
            if os.path.isfile(local_path):
                os.remove(local_path)
        except OSError:
            logging.exception("Failed to remove local face image %s", local_path)

    try:
        _refresh_recognizer()
    except Exception:
        logging.exception("Failed to refresh recognizer after deleting %s", s_id)

    return jsonify({"message": "Visitor and face image successfully deleted."})