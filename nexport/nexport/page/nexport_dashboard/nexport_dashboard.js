// Copyright (c) 2026, NexPort and contributors
// NexPort Risk Dashboard — role-differentiated homepage

frappe.pages["nexport-dashboard"].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "NexPort Dashboard",
		single_column: true,
	});
	new NexportDashboard(page);
};

class NexportDashboard {
	constructor(page) {
		this.page = page;
		this.roles = frappe.get_roles ? frappe.get_roles() : [];
		this._render();
	}

	// ── Role helpers ─────────────────────────────────────
	_isAdmin()       { return this.roles.includes("NexPort Admin") || this.roles.includes("System Manager"); }
	_isFinance()     { return this.roles.includes("NexPort Finance")     || this._isAdmin(); }
	_isWarehouse()   { return this.roles.includes("NexPort Warehouse")   || this._isAdmin(); }
	_isProcurement() { return this.roles.includes("NexPort Procurement") || this._isAdmin(); }

	_roleLabel() {
		if (this._isAdmin())       return "Admin";
		if (this._isFinance())     return "Finance";
		if (this._isWarehouse())   return "Warehouse";
		if (this._isProcurement()) return "Procurement";
		return "User";
	}

	// ── Bootstrap ────────────────────────────────────────
	_render() {
		this.page.main.html(`
			<div class="nx-dashboard" id="nx-root">
				${this._tplGreeting()}
				<div id="nx-banner"></div>
				${this._tplSectionHeader("🔴 Critical Risk")}
				<div class="nx-card-grid" id="nx-critical"></div>
				${this._tplSectionHeader("High-Priority KPIs")}
				<div class="nx-card-grid" id="nx-kpis"></div>
				${this._tplSectionHeader("Actionable To-Dos")}
				<div id="nx-todos"></div>
				${this._tplSectionHeader("Analytics")}
				<div class="nx-card-grid" id="nx-analytics"></div>
			</div>
		`);

		frappe.require([
			"/assets/nexport/css/nexport_dashboard.css",
		], () => {});

		this._loadAll();
	}

	_tplGreeting() {
		const now = new Date();
		const dateStr = now.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
		const hour = now.getHours();
		const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
		const name = frappe.session.user_fullname || frappe.session.user;
		return `
			<div class="nx-greeting">
				<h2>${greeting}, ${name}</h2>
				<span class="nx-date">${dateStr}</span>
				<span class="nx-role-chip">${this._roleLabel()}</span>
			</div>
		`;
	}

	_tplSectionHeader(label) {
		return `<div class="nx-section-header">${label}</div>`;
	}

	// ── Data loading ─────────────────────────────────────
	_loadAll() {
		this._loadCritical();
		this._loadKpis();
		this._loadTodos();
		this._loadAnalytics();
	}

	_call(method, callback) {
		frappe.call({
			method: method,
			callback: (r) => {
				if (r && r.message !== undefined) {
					callback(null, r.message);
				} else {
					callback(new Error("No data"), null);
				}
			},
			error: (err) => callback(err, null),
		});
	}

	// ── SECTION A: Critical Risk ──────────────────────────
	_loadCritical() {
		const container = document.getElementById("nx-critical");
		const cards = [];

		// C8: Gap expiry
		if (this._isAdmin() || this._isFinance() || this._isProcurement()) {
			cards.push(this._cardGapExpiry(container));
		}

		// C9: Cost deviation
		if (this._isAdmin() || this._isFinance()) {
			cards.push(this._cardCostDeviation(container));
		}

		Promise.all(cards).then((results) => {
			const criticalCount = results.reduce((n, r) => n + (r || 0), 0);
			this._renderBanner(criticalCount);
		});
	}

	_cardGapExpiry(container) {
		return new Promise((resolve) => {
			const slot = this._appendSlot(container, "nx-card border-critical");
			slot.innerHTML = this._tplCardLoading("Customs Gap Expiry");

			frappe.call({
				method: "frappe.client.get_list",
				args: {
					doctype: "Customs Gap",
					filters: [
						["status", "!=", "Resolved"],
						["deadline", "<", frappe.datetime.add_days(frappe.datetime.get_today(), 7)],
					],
					fields: ["name", "general_name", "deadline", "gap_qty", "resolved_qty"],
					order_by: "deadline asc",
					limit: 5,
				},
				callback: (r) => {
					const gaps = r.message || [];
					if (gaps.length === 0) {
						slot.innerHTML = this._tplCardOk("Customs Gap Expiry", "No gaps expiring soon");
						resolve(0);
						return;
					}
					const rows = gaps.map((g) => {
						const open = (g.gap_qty || 0) - (g.resolved_qty || 0);
						const deadline = frappe.datetime.str_to_obj(g.deadline);
						const days = Math.ceil((deadline - new Date()) / 86400000);
						const daysLabel = days < 0 ? "Expired" : `${days}d left`;
						return `
							<div class="nx-gap-row">
								<span style="flex:1">${frappe.utils.escape_html(g.general_name || g.name)}</span>
								<span class="nx-gap-deadline">${daysLabel}</span>
								<span style="color:#6B7280">${open} units</span>
								<a class="nx-btn nx-btn-critical" href="/app/customs-gap/${encodeURIComponent(g.name)}"
									style="padding:4px 10px;font-size:12px;min-height:32px">Resolve →</a>
							</div>`;
					}).join("");
					slot.innerHTML = `
						${this._tplCardHeader("🔴 Customs Gap Expiry", "critical", `${gaps.length} gap${gaps.length > 1 ? "s" : ""} < 7 days`)}
						<div>${rows}</div>
						${this._tplCta("View All Expiring Gaps →", "/app/customs-gap?status%5B%5D=Pending&status%5B%5D=Partial&orderBy=deadline+ASC", "critical")}
					`;
					resolve(gaps.length);
				},
				error: () => { slot.innerHTML = this._tplCardError("Customs Gap Expiry"); resolve(0); },
			});
		});
	}

	_cardCostDeviation(container) {
		return new Promise((resolve) => {
			const slot = this._appendSlot(container, "nx-card border-critical");
			slot.innerHTML = this._tplCardLoading("Cost Deviation");

			frappe.call({
				method: "nexport.nexport.page.nexport_dashboard.nexport_dashboard.get_cost_deviations",
				callback: (r) => {
					const items = r.message || [];
					if (items.length === 0) {
						slot.innerHTML = this._tplCardOk("Cost Deviation", "No items exceed 10% deviation");
						resolve(0);
						return;
					}
					const rows = items.slice(0, 4).map((it) => {
						const pct = (it.deviation_pct || 0).toFixed(1);
						const cls = it.deviation_pct > 20 ? "critical" : "high";
						return `
							<div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--color-border)">
								<span style="flex:1;font-size:13px">${frappe.utils.escape_html(it.item_name || it.name)}</span>
								<span class="nx-badge ${cls}">${pct}%</span>
								<a class="nx-btn nx-btn-outline" href="/app/item/${encodeURIComponent(it.name)}"
									style="padding:4px 10px;font-size:12px;min-height:32px">Review →</a>
							</div>`;
					}).join("");
					slot.innerHTML = `
						${this._tplCardHeader("🔴 Cost Deviation", "critical", `${items.length} item${items.length > 1 ? "s" : ""} > 10% over estimate`)}
						<div>${rows}</div>
						${this._tplCta("Review Cost Items →", "/app/inventory-dual-track", "critical")}
					`;
					resolve(items.length);
				},
				error: () => { slot.innerHTML = this._tplCardError("Cost Deviation"); resolve(0); },
			});
		});
	}

	// ── SECTION B: KPI Cards ──────────────────────────────
	_loadKpis() {
		const container = document.getElementById("nx-kpis");

		// Quick Actions always in last col-3
		const qaSlot = this._appendSlot(container, "nx-card");

		if (this._isAdmin() || this._isFinance() || this._isWarehouse() || this._isProcurement()) {
			this._cardInventory(container);
		}
		if (this._isAdmin() || this._isFinance() || this._isProcurement()) {
			this._cardCustomsGaps(container);
		}
		if (this._isAdmin() || this._isFinance()) {
			this._cardApInvoices(container);
		}

		// Quick Actions card (always last)
		qaSlot.innerHTML = this._buildQuickActions();
	}

	_cardInventory(container) {
		const slot = this._appendSlot(container, "nx-card");
		slot.innerHTML = this._tplCardLoading("Inventory");

		frappe.call({
			method: "nexport.nexport.page.nexport_dashboard.nexport_dashboard.get_inventory_summary",
			callback: (r) => {
				const d = r.message || {};
				const phys = d.phys_val || 0;
				const decl = d.decl_val || 0;
				const gap = phys - decl;
				const gapPct = phys ? (gap / phys * 100).toFixed(1) : 0;
				const sev = gapPct > 15 ? "critical" : gapPct > 5 ? "high" : "ok";

				const showTHB = this._isAdmin() || this._isFinance();
				const showDeclared = this._isAdmin() || this._isFinance() || this._isProcurement();

				slot.innerHTML = `
					${this._tplCardHeader("Inventory Dual-Track", sev)}
					<div class="nx-card-kpi">${showTHB ? "฿ " + this._fmt(phys) : this._fmt(d.phys_qty || 0) + " units"}</div>
					<div class="nx-card-sub">
						${showTHB ? `<span><span>Physical</span><span>฿ ${this._fmt(phys)}</span></span>` : ""}
						${showDeclared && showTHB ? `<span><span>Declared</span><span>฿ ${this._fmt(decl)}</span></span>` : ""}
						${showTHB ? `<span><span>Gap</span><span class="nx-badge ${sev}">฿ ${this._fmt(gap)} (${gapPct}%)</span></span>` : ""}
					</div>
					${this._tplCta("View Item Costs →", "/app/inventory-dual-track", sev)}
				`;
			},
			error: () => { slot.innerHTML = this._tplCardError("Inventory"); },
		});
	}

	_cardCustomsGaps(container) {
		const slot = this._appendSlot(container, "nx-card");
		slot.innerHTML = this._tplCardLoading("Customs Gaps");

		frappe.call({
			method: "nexport.nexport.page.nexport_dashboard.nexport_dashboard.get_customs_gap_summary",
			callback: (r) => {
				const d = r.message || {};
				const near = d.near_expiry || 0;
				const total = d.total || 0;
				const sev = near > 0 ? "critical" : total > 10 ? "high" : "medium";

				if (total === 0) {
					slot.innerHTML = this._tplCardOk("Customs Gaps", `All gaps resolved ✅<br><small style="color:#9CA3AF">Last resolved: ${d.last_resolved || "—"}</small>`);
					return;
				}
				slot.innerHTML = `
					${this._tplCardHeader("Customs Gaps", sev)}
					<div class="nx-card-kpi">${total} <span style="font-size:18px;font-weight:400">gaps</span></div>
					<div class="nx-card-sub">
						<span><span>Open quantity</span><span>${this._fmt(d.open_qty || 0)} units</span></span>
						<span><span>Near-expiry</span><span class="nx-badge ${near > 0 ? "critical" : "ok"}">${near} in < 7 days</span></span>
					</div>
					${this._tplCta("Reconcile Gaps →", "/app/customs-gap?status%5B%5D=Pending&status%5B%5D=Partial&orderBy=deadline+ASC", sev)}
				`;
			},
			error: () => { slot.innerHTML = this._tplCardError("Customs Gaps"); },
		});
	}

	_cardApInvoices(container) {
		const slot = this._appendSlot(container, "nx-card");
		slot.innerHTML = this._tplCardLoading("AP Invoices");

		frappe.call({
			method: "nexport.nexport.page.nexport_dashboard.nexport_dashboard.get_ap_invoice_summary",
			callback: (r) => {
				const d = r.message || {};
				const overdue = d.overdue || 0;
				const prov = d.provisional || 0;
				const sev = overdue > 0 ? "critical" : prov > 0 ? "high" : "medium";

				slot.innerHTML = `
					${this._tplCardHeader("Pending AP Invoices", sev)}
					<div class="nx-card-kpi">฿ ${this._fmt(d.overdue_amount || 0)}</div>
					<div class="nx-card-sub">
						<span><span>Overdue invoices</span><span class="nx-badge ${sev}">${overdue}</span></span>
						<span><span>Provisional</span><span class="nx-badge ${prov > 0 ? "high" : "ok"}">${prov}</span></span>
						<span><span>Total outstanding</span><span>฿ ${this._fmt(d.total_outstanding || 0)}</span></span>
					</div>
					${this._tplCta("Convert Invoices →", "/app/invoice?type=AP&is_provisional=1", sev)}
				`;
			},
			error: () => { slot.innerHTML = this._tplCardError("AP Invoices"); },
		});
	}

	_buildQuickActions() {
		const btns = [];
		if (this._isAdmin() || this._isProcurement()) {
			btns.push(`<a class="nx-btn nx-btn-primary" href="/app/purchase-order/new-purchase-order-1">+ PO</a>`);
		}
		if (this._isAdmin() || this._isWarehouse() || this._isProcurement()) {
			btns.push(`<a class="nx-btn nx-btn-primary" href="/app/shipment/new-shipment-1">+ Shipment</a>`);
		}
		if (this._isAdmin() || this._isFinance() || this._isProcurement()) {
			btns.push(`<a class="nx-btn nx-btn-primary" href="/app/customs-gap/new-customs-gap-1">+ Gap</a>`);
		}
		btns.push(`<a class="nx-btn nx-btn-outline" href="/app/query-report/Inventory%20Dual-Track">Reports</a>`);
		return `
			${this._tplCardHeader("Quick Actions", "ok")}
			<div class="nx-quick-actions">${btns.join("")}</div>
		`;
	}

	// ── SECTION C: To-Dos ────────────────────────────────
	_loadTodos() {
		const container = document.getElementById("nx-todos");
		container.innerHTML = `<div class="nx-card-grid">
			<div class="nx-card half" id="nx-todo-list-wrap"></div>
			<div class="nx-card" id="nx-shipment-wrap"></div>
		</div>`;

		this._buildTodoList(document.getElementById("nx-todo-list-wrap"));
		this._buildShipmentTracker(document.getElementById("nx-shipment-wrap"));
	}

	_buildTodoList(container) {
		container.innerHTML = `
			${this._tplCardHeader("Actionable To-Dos", "high")}
			<div class="nx-todo-list" id="nx-todo-rows"><div style="color:#9CA3AF;font-size:13px">Loading…</div></div>
			<div style="padding-top:10px;text-align:right">
				<a class="nx-btn nx-btn-outline" href="/app/query-report">See all To-Dos →</a>
			</div>
		`;

		const todoRows = document.getElementById("nx-todo-rows");
		const todos = [];

		// Convert provisional invoices (Finance/Admin) — field added in issue #6
		if (this._isAdmin() || this._isFinance()) {
			todos.push(
				frappe.call({
					method: "frappe.client.get_count",
					args: { doctype: "Invoice", filters: [["type", "=", "AP"], ["is_provisional", "=", 1], ["status", "!=", "Paid"]] },
					callback: (r) => {
						if ((r.message || 0) > 0) {
							this._appendTodo(todoRows, "high",
								`Convert ${r.message} Provisional Invoice${r.message > 1 ? "s" : ""}`,
								"/app/invoice?type=AP&is_provisional=1",
								"Convert Now");
						}
					},
					error: () => { /* is_provisional not yet available */ },
				})
			);
		}

		// Confirm supplementary POs (Procurement/Admin) — field added in issue #7
		if (this._isAdmin() || this._isProcurement()) {
			todos.push(
				frappe.call({
					method: "frappe.client.get_count",
					args: { doctype: "Purchase Order", filters: [["is_supplementary", "=", 1], ["status", "=", "Draft"]] },
					callback: (r) => {
						if ((r.message || 0) > 0) {
							this._appendTodo(todoRows, "high",
								`Confirm ${r.message} Supplementary PO${r.message > 1 ? "s" : ""}`,
								"/app/purchase-order?is_supplementary=1&status=Draft",
								"Review PO");
						}
					},
					error: () => { /* is_supplementary not yet available */ },
				})
			);
		}

		// FIFO reconcile (Admin/Finance/Procurement)
		if (this._isAdmin() || this._isFinance() || this._isProcurement()) {
			todos.push(
				frappe.call({
					method: "nexport.nexport.page.nexport_dashboard.nexport_dashboard.get_fifo_reconcile_count",
					callback: (r) => {
						const cnt = r.message || 0;
						if (cnt > 0) {
							this._appendTodo(todoRows, "medium",
								`FIFO Reconcile: ${cnt} item${cnt > 1 ? "s" : ""} ready`,
								"/app/customs-gap?status%5B%5D=Pending&status%5B%5D=Partial",
								"Reconcile");
						}
					},
				})
			);
		}

		// POs shipped, awaiting receipt (Warehouse/Admin/Procurement)
		if (this._isAdmin() || this._isWarehouse() || this._isProcurement()) {
			todos.push(
				frappe.call({
					method: "frappe.client.get_count",
					args: { doctype: "Shipment", filters: [["status", "in", ["In Transit", "Arrived at Port"]]] },
					callback: (r) => {
						if ((r.message || 0) > 0) {
							this._appendTodo(todoRows, "medium",
								`${r.message} shipment${r.message > 1 ? "s" : ""} awaiting receipt`,
								"/app/shipment?status%5B%5D=In+Transit&status%5B%5D=Arrived",
								"View Shipments");
						}
					},
				})
			);
		}

		Promise.all(todos).then(() => {
			const rows = todoRows.querySelectorAll(".nx-todo-row");
			if (rows.length === 0) {
				todoRows.innerHTML = `<div style="color:var(--color-ok);font-size:13px;padding:8px 0">✅ All tasks complete — nothing pending!</div>`;
			}
		});
	}

	_appendTodo(container, sev, text, href, btnLabel) {
		// Remove loading placeholder on first item
		const placeholder = container.querySelector("div:not(.nx-todo-row)");
		if (placeholder) placeholder.remove();

		const row = document.createElement("div");
		row.className = "nx-todo-row";
		const icon = sev === "high" ? "🟠" : "🟡";
		row.innerHTML = `
			<span>${icon}</span>
			<span class="nx-todo-text">${frappe.utils.escape_html(text)}</span>
			<a class="nx-btn nx-btn-${sev}" href="${href}" style="white-space:nowrap">${btnLabel} →</a>
		`;
		container.appendChild(row);
	}

	_buildShipmentTracker(container) {
		container.innerHTML = this._tplCardLoading("Shipments in Transit");

		frappe.call({
			method: "nexport.nexport.page.nexport_dashboard.nexport_dashboard.get_shipment_modes",
			callback: (r) => {
				const modes = r.message || [];
				if (modes.length === 0) {
					container.innerHTML = this._tplCardOk("Shipments", "No active shipments");
					return;
				}
				const rows = modes.map((m) => {
					const icon = m.delay_count > 0 ? "⚠️" : "✓";
					return `
						<div class="nx-shipment-mode">
							<span>${frappe.utils.escape_html(m.mode)}</span>
							<span>${m.total} ${icon}</span>
						</div>`;
				}).join("");
				container.innerHTML = `
					${this._tplCardHeader("Shipments in Transit", "ok")}
					<div>${rows}</div>
					${this._tplCta("Track All →", "/app/shipment?status%5B%5D=In+Transit&status%5B%5D=Arrived", "ok")}
				`;
			},
			error: () => { container.innerHTML = this._tplCardError("Shipments"); },
		});
	}

	// ── SECTION D: Analytics ─────────────────────────────
	_loadAnalytics() {
		const container = document.getElementById("nx-analytics");

		if (this._isAdmin() || this._isFinance()) {
			this._cardCashFlow(container);
		}

		this._cardPoFunnel(container);

		if (this._isAdmin() || this._isFinance()) {
			this._cardPriceWatchlist(container);
		}
	}

	_cardCashFlow(container) {
		const slot = this._appendSlot(container, "nx-card");
		slot.innerHTML = this._tplCardLoading("Cash Flow (30 days)");

		frappe.call({
			method: "nexport.nexport.page.nexport_dashboard.nexport_dashboard.get_cash_flow_summary",
			callback: (r) => {
				const d = r.message || {};
				slot.innerHTML = `
					${this._tplCardHeader("Cash Flow Forecast", "medium")}
					<div class="nx-card-sub">
						<span><span>AP due (30 days)</span><span>฿ ${this._fmt(d.ap_due || 0)}</span></span>
						<span><span>Duty estimate</span><span>฿ ${this._fmt(d.duty_est || 0)}</span></span>
						<span><span style="font-weight:600">Net requirement</span>
							<span style="font-weight:600">฿ ${this._fmt((d.ap_due || 0) + (d.duty_est || 0))}</span></span>
					</div>
					${this._tplCta("Cash Flow Report →", "/app/query-report/Cash%20Flow%2030%20Day", "medium")}
				`;
			},
			error: () => { slot.innerHTML = this._tplCardError("Cash Flow"); },
		});
	}

	_cardPoFunnel(container) {
		const slot = this._appendSlot(container, "nx-card");
		slot.innerHTML = this._tplCardLoading("PO Status Funnel");

		frappe.call({
			method: "nexport.nexport.page.nexport_dashboard.nexport_dashboard.get_po_status_summary",
			callback: (r) => {
				const statuses = r.message || [];
				const rows = statuses.map((s) => {
					const pct = s.max ? Math.round(s.count / s.max * 100) : 0;
					const bar = "▓".repeat(Math.round(pct / 10)).padEnd(4, "░");
					return `
						<div style="display:flex;align-items:center;gap:8px;padding:4px 0;font-size:13px">
							<span style="width:80px;color:#6B7280">${frappe.utils.escape_html(s.status)}</span>
							<span style="color:#374151;letter-spacing:-1px">${bar}</span>
							<span style="margin-left:auto;font-weight:500">${s.count}</span>
						</div>`;
				}).join("");
				slot.innerHTML = `
					${this._tplCardHeader("PO Status Funnel", "ok")}
					<div>${rows}</div>
					${this._tplCta("Open PO List →", "/app/purchase-order", "ok")}
				`;
			},
			error: () => { slot.innerHTML = this._tplCardError("PO Funnel"); },
		});
	}

	_cardPriceWatchlist(container) {
		const slot = this._appendSlot(container, "nx-card");
		slot.innerHTML = this._tplCardLoading("Price Deviation Watchlist");

		frappe.call({
			method: "nexport.nexport.page.nexport_dashboard.nexport_dashboard.get_cost_deviations",
			callback: (r) => {
				const items = (r.message || []).slice(0, 5);
				if (items.length === 0) {
					slot.innerHTML = this._tplCardOk("Price Watchlist", "No cost deviations detected");
					return;
				}
				const rows = items.map((it) => {
					const pct = (it.deviation_pct || 0).toFixed(1);
					const sign = it.deviation_pct >= 0 ? "+" : "";
					const cls = Math.abs(it.deviation_pct) > 20 ? "critical" : "high";
					return `
						<div style="display:flex;align-items:center;gap:8px;padding:4px 0;font-size:13px;border-bottom:1px solid var(--color-border)">
							<span style="flex:1">${frappe.utils.escape_html(it.item_name || it.name)}</span>
							<span class="nx-badge ${cls}">${sign}${pct}%</span>
						</div>`;
				}).join("");
				slot.innerHTML = `
					${this._tplCardHeader("Price Deviation Watchlist", "high")}
					<div>${rows}</div>
					${this._tplCta("Cost Report →", "/app/query-report/Inventory%20Dual-Track", "high")}
				`;
			},
			error: () => { slot.innerHTML = this._tplCardError("Price Watchlist"); },
		});
	}

	// ── Alert Banner ─────────────────────────────────────
	_renderBanner(criticalCount) {
		const el = document.getElementById("nx-banner");
		if (criticalCount === 0) {
			el.innerHTML = `
				<div class="nx-alert-banner ok" onclick="document.getElementById('nx-kpis').scrollIntoView({behavior:'smooth'})">
					✅ No critical risks today — all systems normal
					<span class="nx-banner-arrow">↓</span>
				</div>`;
		} else {
			el.innerHTML = `
				<div class="nx-alert-banner critical" onclick="document.getElementById('nx-critical').scrollIntoView({behavior:'smooth'})">
					🔴 ${criticalCount} critical issue${criticalCount > 1 ? "s" : ""} require immediate attention
					<span class="nx-banner-arrow">↓ View</span>
				</div>`;
		}
	}

	// ── Template helpers ──────────────────────────────────
	_tplCardHeader(title, sev, subtitle) {
		const icons = { critical: "🔴", high: "🟠", medium: "🟡", ok: "✅" };
		return `
			<div class="nx-card-label">${icons[sev] || ""} ${frappe.utils.escape_html(title)}</div>
			${subtitle ? `<div style="font-size:12px;color:#6B7280">${frappe.utils.escape_html(subtitle)}</div>` : ""}
		`;
	}

	_tplCta(label, href, sev) {
		const cls = sev === "critical" ? "nx-btn-critical" : sev === "high" ? "nx-btn-high" : sev === "ok" ? "nx-btn-primary" : "nx-btn-outline";
		return `
			<div class="nx-card-cta">
				<a class="nx-btn ${cls}" href="${href}">${frappe.utils.escape_html(label)}</a>
			</div>`;
	}

	_tplCardLoading(title) {
		return `<div class="nx-card-label">${frappe.utils.escape_html(title)}</div>
				<div style="color:#9CA3AF;font-size:13px">Loading…</div>`;
	}

	_tplCardOk(title, msg) {
		return `
			${this._tplCardHeader(title, "ok")}
			<div style="color:var(--color-ok);font-size:14px;padding:8px 0">${msg}</div>
		`;
	}

	_tplCardError(title) {
		return `
			<div class="nx-card-label">${frappe.utils.escape_html(title)}</div>
			<div class="nx-card-error">⚠️ Data unavailable
				<button class="nx-btn nx-btn-outline" onclick="location.reload()" style="padding:4px 10px;font-size:12px">Refresh</button>
			</div>`;
	}

	_appendSlot(container, cls) {
		const div = document.createElement("div");
		div.className = cls;
		container.appendChild(div);
		return div;
	}

	_fmt(n) {
		return (n || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });
	}
}
