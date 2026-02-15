frappe.pages["policy-file-view"].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Policy Viewer",
		single_column: true,
	});

	// Get URL parameters
	const urlParams = new URLSearchParams(window.location.search);
	const policyDocumentId = urlParams.get("policy_document");
	const motorPolicyId = urlParams.get("motor_policy");

	if (!policyDocumentId) {
		page.main.html(`
			<div class="text-center pfv-centered-message">
				<h3>No Policy Document Selected</h3>
				<p>Please select a policy document to view.</p>
			</div>
		`);
		return;
	}

	// Load policy document data and render split pane
	loadPolicyDocument(page, policyDocumentId, motorPolicyId);
};

function loadPolicyDocument(page, policyDocumentId, motorPolicyId) {
	// Show loading state
	page.main.html(`
		<div class="text-center pfv-centered-message">
			<div class="spinner-border" role="status">
				<span class="sr-only">Loading...</span>
			</div>
			<p class="mt-3">Loading documents...</p>
		</div>
	`);

	// Prepare API calls
	const apiCalls = [
		frappe.call({
			method: "frappe.client.get",
			args: {
				doctype: "Policy Document",
				name: policyDocumentId,
			},
		}),
	];

	// Add Motor Policy call if ID is provided
	if (motorPolicyId) {
		apiCalls.push(
			frappe.call({
				method: "frappe.client.get",
				args: {
					doctype: "Motor Policy",
					name: motorPolicyId,
				},
			})
		);
	}

	// Handle API calls differently - use individual callbacks instead of Promise.all
	let policyDoc = null;
	let motorPolicy = null;
	let completedCalls = 0;
	const totalCalls = motorPolicyId ? 2 : 1;

	// Function to check if all calls are complete
	function checkComplete() {
		completedCalls++;
		if (completedCalls === totalCalls) {
			if (policyDoc) {
				renderSplitPane(page, policyDoc, motorPolicy);
			} else {
				page.main.html(`
					<div class="text-center pfv-centered-message">
						<h3>Error Loading Document</h3>
						<p>Could not load policy document: ${policyDocumentId}</p>
					</div>
				`);
			}
		}
	}

	// Load Policy Document
	frappe.call({
		method: "frappe.client.get",
		args: {
			doctype: "Policy Document",
			name: policyDocumentId,
		},
		callback: function (r) {
			if (r.message) {
				policyDoc = r.message;
			}
			checkComplete();
		},
		error: function (err) {
			console.error("Policy Document load error:", err);
			page.main.html(`
				<div class="text-center pfv-centered-message">
					<h3>Error Loading Policy Document</h3>
					<p>Failed to load policy document: ${err.message || "Unknown error"}</p>
				</div>
			`);
		},
	});

	// Load Motor Policy if ID provided
	if (motorPolicyId) {
		frappe.call({
			method: "frappe.client.get",
			args: {
				doctype: "Motor Policy",
				name: motorPolicyId,
			},
			callback: function (r) {
				if (r.message) {
					motorPolicy = r.message;
				}
				checkComplete();
			},
			error: function (err) {
				console.error("Motor Policy load error:", err);
				// Don't fail completely, just proceed without Motor Policy
				checkComplete();
			},
		});
	}
}

function renderSplitPane(page, policyDoc, motorPolicy) {
	// Generate content for the right pane
	const rightPaneContent = motorPolicy
		? renderMotorPolicyFields(motorPolicy, policyDoc)
		: formatExtractedFields(policyDoc);
	console.log("Right pane content length:", rightPaneContent.length);

	// Create split pane layout
	page.main.html(`
		<!-- Header with Policy Document Link -->
		<div class="policy-header">
			<div class="d-flex justify-content-between align-items-center">
				<div>
					<div class="d-flex align-items-center mb-2">
						<button class="btn btn-outline-secondary btn-sm mr-3" onclick="window.close()" title="Close this tab">
							<i class="fa fa-times"></i> Close
						</button>
						<h4 class="mb-0">${policyDoc.title || "Policy Document"}</h4>
					</div>
					<p class="mb-0 text-muted">
						Policy Type: <span class="badge badge-primary">${policyDoc.policy_type}</span>
						<span class="mx-2">|</span>
						Status: <span class="badge badge-${getStatusBadgeClass(policyDoc.status)}">${
		policyDoc.status
	}</span>
						<span class="mx-2">|</span>
						Processing Method: <span class="badge badge-info">${policyDoc.processing_method || "N/A"}</span>
					</p>
				</div>
				<div>
					<a href="/app/policy-document/${
						policyDoc.name
					}" class="btn btn-outline-primary btn-sm" target="_blank">
						<i class="fa fa-external-link"></i> View Policy Document
					</a>
				</div>
			</div>
		</div>

		<div class="policy-viewer-container">
			<!-- PDF Viewer Pane -->
			<div class="pdf-pane">
				<div class="pane-header">
					<h5 class="mb-0">PDF Document</h5>
					<div class="pdf-controls">
						<button class="btn btn-sm btn-outline-secondary" id="zoom-out">-</button>
						<span id="zoom-level" class="mx-2">100%</span>
						<button class="btn btn-sm btn-outline-secondary" id="zoom-in">+</button>
					</div>
				</div>
				<div class="pdf-container">
					<div id="pdf-viewer">
						<div class="text-center">
							<div class="spinner-border" role="status">
								<span class="sr-only">Loading PDF...</span>
							</div>
							<p class="mt-3">Loading PDF...</p>
						</div>
					</div>
				</div>
			</div>

			<!-- Resize Handle -->
			<div class="resize-handle" title="Drag to resize">
				<div class="resize-handle-indicator"></div>
			</div>

			<!-- Motor Policy Fields Pane -->
			<div class="fields-pane">
				<div class="pane-header">
					<h5 class="mb-0">${motorPolicy ? "Motor Policy Fields" : "Extracted Fields"}</h5>
					<div class="fields-controls">
						${
							motorPolicy
								? `<button class="btn btn-sm btn-outline-primary" id="save-policy">Save Changes</button>
							 <button class="btn btn-sm btn-outline-info" id="refresh-policy">Refresh</button>
							 <button class="btn btn-sm btn-outline-secondary" id="toggle-extracted">Show Extracted</button>`
								: `<button class="btn btn-sm btn-outline-secondary" id="toggle-view">Show Raw Text</button>
							 <button class="btn btn-sm btn-outline-secondary" id="copy-fields">Copy</button>`
						}
					</div>
				</div>
				<div class="fields-container">
					<div id="policy-fields-content">
						<!-- Content will be inserted here -->
					</div>
				</div>
			</div>
		</div>

	`);

	// Insert the right pane content after DOM is created with error handling
	const contentDiv = document.getElementById("policy-fields-content");
	if (contentDiv) {
		try {
			contentDiv.innerHTML = rightPaneContent;
		} catch (error) {
			console.error("Error setting innerHTML:", error);
			contentDiv.innerHTML =
				'<div class="alert alert-danger">Error loading form fields. Please refresh and try again.</div>';
		}
	}

	// Load PDF
	loadPDF(policyDoc.policy_file);

	// Setup event handlers
	setupEventHandlers(policyDoc, motorPolicy);
}

function getStatusBadgeClass(status) {
	const statusClasses = {
		Draft: "secondary",
		Processing: "warning",
		Completed: "success",
		Failed: "danger",
	};
	return statusClasses[status] || "secondary";
}

function formatExtractedFields(policyDoc) {
	if (!policyDoc.extracted_fields) {
		return `
			<div class="text-center text-muted pfv-no-data-message">
				<i class="fa fa-exclamation-triangle fa-3x mb-3"></i>
				<h5>No Extracted Fields Available</h5>
				<p>This document hasn't been processed yet or extraction failed.</p>
			</div>
		`;
	}

	try {
		const extractedData =
			typeof policyDoc.extracted_fields === "string"
				? JSON.parse(policyDoc.extracted_fields)
				: policyDoc.extracted_fields;

		if (!extractedData || Object.keys(extractedData).length === 0) {
			return `
				<div class="text-center text-muted pfv-no-data-message">
					<i class="fa fa-info-circle fa-3x mb-3"></i>
					<h5>No Fields Extracted</h5>
					<p>The extraction process completed but no fields were found.</p>
				</div>
			`;
		}

		return renderFieldsTable(extractedData, policyDoc);
	} catch (error) {
		console.error("Error formatting extracted fields:", error);
		return `
			<div class="alert alert-danger">
				<i class="fa fa-exclamation-triangle"></i>
				<strong>Error:</strong> Could not parse extracted fields data.
			</div>
		`;
	}
}

/**
 * Simple function to render extracted fields as a clean table
 * @param {Object} extractedData - The extracted fields JSON data
 * @param {Object} policyDoc - The policy document object (for metadata)
 * @returns {string} HTML string for the rendered table
 */
function renderFieldsTable(extractedData, policyDoc = {}) {
	let html = '<div class="extracted-fields-table">';

	// Add confidence score if available
	if (policyDoc && policyDoc.ocr_confidence) {
		html += `
			<div class="alert alert-info mb-3">
				<i class="fa fa-chart-line"></i>
				<strong>OCR Confidence:</strong> ${Math.round(policyDoc.ocr_confidence * 100)}%
				${
					policyDoc && policyDoc.manual_review_recommended
						? '<span class="badge badge-warning ml-2">Manual Review Recommended</span>'
						: ""
				}
			</div>
		`;
	}

	// Create simple fields container
	html += `
		<div class="fields-simple-section">
			<div class="fields-header">
				<h5 class="mb-0">
					<i class="fa fa-list"></i> Extracted Fields
				</h5>
			</div>
			<div class="fields-content">
	`;

	// Render fields from data (handles both flat and nested structures)
	html += renderDataRows(extractedData);

	html += `
			</div>
		</div>
	</div>`;

	return html;
}

/**
 * Recursively render data rows for both flat and nested structures
 * @param {Object} data - The data object to render
 * @param {string} prefix - Optional prefix for nested fields
 * @returns {string} HTML string for the rows
 */
function renderDataRows(data, prefix = "") {
	let html = "";

	Object.keys(data).forEach((key) => {
		const value = data[key];
		const displayKey = prefix ? `${prefix} > ${key}` : key;

		if (value && typeof value === "object" && !Array.isArray(value)) {
			// Nested object - render with prefix
			html += renderDataRows(value, displayKey);
		} else {
			// Simple key-value pair - cleaner line format
			html += `
				<div class="extracted-field-row">
					<div class="extracted-field-label">
						${formatFieldLabel(displayKey)}:
					</div>
					<div class="extracted-field-value">
						${formatFieldValue(value)}
					</div>
				</div>
			`;
		}
	});

	return html;
}

/**
 * Format field label for display
 * @param {string} fieldName - The field name
 * @returns {string} Formatted field label
 */
function formatFieldLabel(fieldName) {
	// Convert snake_case to Title Case
	return fieldName
		.replace(/_/g, " ")
		.replace(/\b\w/g, (l) => l.toUpperCase())
		.replace(/\b(No|Id|Code|Gst|Ncb|Cc|Rto)\b/g, (l) => l.toUpperCase());
}

function formatFieldValue(value) {
	// Handle null, undefined, None, or empty values
	if (
		!value ||
		value === "null" ||
		value === "undefined" ||
		value === "None" ||
		value === null ||
		value === undefined
	) {
		return '<span class="text-muted"><i class="fa fa-minus"></i> Not available</span>';
	}

	// Convert to string for processing
	const stringValue = String(value).trim();

	// Handle empty strings
	if (stringValue === "" || stringValue === "None") {
		return '<span class="text-muted"><i class="fa fa-minus"></i> Not available</span>';
	}

	// Format dates (basic patterns)
	if (
		typeof value === "string" &&
		(/^\d{4}-\d{2}-\d{2}$/.test(stringValue) || /^\d{1,2}\/\d{1,2}\/\d{4}$/.test(stringValue))
	) {
		return `<span class="text-primary"><i class="fa fa-calendar"></i> ${stringValue}</span>`;
	}

	// Format currency amounts
	if (
		(typeof value === "number" && value > 0) ||
		(typeof value === "string" && /^₹?[\d,]+/.test(stringValue))
	) {
		return `<span class="text-success"><i class="fa fa-rupee"></i> ${stringValue}</span>`;
	}

	// Default formatting for regular text
	return `<span class="text-dark">${stringValue}</span>`;
}

/**
 * Render Motor Policy fields as editable form
 * @param {Object} motorPolicy - The Motor Policy document
 * @param {Object} policyDoc - The Policy Document (for extracted data hints)
 * @returns {string} HTML string for the form fields
 */
function renderMotorPolicyFields(motorPolicy, policyDoc) {
	// Extract data for hints
	let extractedData = {};
	try {
		if (policyDoc.extracted_fields) {
			extractedData =
				typeof policyDoc.extracted_fields === "string"
					? JSON.parse(policyDoc.extracted_fields)
					: policyDoc.extracted_fields;
		}
	} catch (e) {
		console.warn("Could not parse extracted fields:", e);
	}

	// Define field groups based on Motor Policy DocType structure
	const fieldGroups = [
		{
			title: "Policy Information",
			icon: "file-text-o",
			fields: [
				{ name: "policy_no", label: "Policy No", type: "text" },
				{ name: "policy_type", label: "Policy Type", type: "text" },
				{ name: "policy_issuance_date", label: "Policy Issuance Date", type: "date" },
				{ name: "policy_start_date", label: "Policy Start Date", type: "date" },
				{ name: "policy_expiry_date", label: "Policy Expiry Date", type: "date" },
			],
		},
		{
			title: "Vehicle Information",
			icon: "car",
			fields: [
				{ name: "vehicle_no", label: "Vehicle No", type: "text" },
				{ name: "make", label: "Make", type: "text" },
				{ name: "model", label: "Model", type: "text" },
				{ name: "variant", label: "Variant", type: "text" },
				{ name: "year_of_man", label: "Year of Manufacture", type: "number" },
				{ name: "chasis_no", label: "Chasis No", type: "text" },
				{ name: "engine_no", label: "Engine No", type: "text" },
				{ name: "cc", label: "CC", type: "text" },
				{ name: "fuel", label: "Fuel", type: "text" },
			],
		},
		{
			title: "Business Information",
			icon: "building",
			fields: [
				{ name: "customer_code", label: "Customer Code", type: "text" },
				{ name: "policy_biz_type", label: "Policy Biz Type", type: "text" },
				{ name: "insurer_branch_code", label: "Insurer Branch Code", type: "number" },
				{
					name: "new_renewal",
					label: "New/Renewal",
					type: "select",
					options: ["New", "Renewal"],
				},
				{ name: "payment_mode", label: "Payment Mode", type: "text" },
				{ name: "bank_name", label: "Bank Name", type: "text" },
				{ name: "payment_transaction_no", label: "Payment Transaction No", type: "text" },
			],
		},
		{
			title: "Financial Details",
			icon: "money",
			fields: [
				{ name: "sum_insured", label: "Sum Insured", type: "float" },
				{ name: "net_od_premium", label: "Net/OD Premium", type: "float" },
				{ name: "tp_premium", label: "TP Premium", type: "float" },
				{ name: "gst", label: "GST", type: "float" },
				{ name: "ncb", label: "NCB", type: "float" },
			],
		},
	];

	let html = '<div class="motor-policy-form">';

	fieldGroups.forEach((group) => {
		html += `
			<div class="field-group mb-4">
				<div class="group-header">
					<h6 class="mb-0">
						<i class="fa fa-${group.icon}"></i> ${group.title}
					</h6>
				</div>
				<div class="group-fields">
					<div class="row">
		`;

		group.fields.forEach((field, index) => {
			const value = motorPolicy[field.name] || "";
			const extractedValue = getExtractedValue(extractedData, field.name, field.label);

			html += `
				<div class="col-md-6 mb-3">
					<label class="form-label">
						${field.label}
						${
							extractedValue
								? '<i class="fa fa-lightbulb-o text-warning ml-1" title="Extracted data available"></i>'
								: ""
						}
					</label>
					${renderFieldInput(field, value, extractedValue)}
					${
						extractedValue && extractedValue !== value
							? `<small class="text-muted">Extracted: <span class="text-info">${escapeQuotes(
									extractedValue
							  )}</span> 
						 <button class="btn btn-xs btn-link p-0 ml-1" data-field="${
								field.name
							}" data-value="${escapeQuotes(
									extractedValue
							  )}" onclick="copyExtractedValueFromButton(this)">Copy</button></small>`
							: ""
					}
				</div>
			`;
		});

		html += `
					</div>
				</div>
			</div>
		`;
	});

	html += "</div>";
	return html;
}

/**
 * Render individual field input based on field type
 */
function renderFieldInput(field, value, extractedValue) {
	const safeValue = escapeQuotes(value || "");
	const safePlaceholder = escapeQuotes(extractedValue || "Enter " + field.label);

	const commonAttrs = `
		id="field-${field.name}" 
		name="${field.name}" 
		class="form-control motor-policy-field" 
		data-fieldname="${field.name}"
		placeholder="${safePlaceholder}"
	`;

	switch (field.type) {
		case "date":
			return `<input type="date" value="${safeValue}" ${commonAttrs}>`;
		case "number":
		case "float":
			return `<input type="number" value="${safeValue}" ${commonAttrs} ${
				field.type === "float" ? 'step="0.01"' : ""
			}>`;
		case "select":
			const options = field.options
				.map(
					(opt) =>
						`<option value="${escapeQuotes(opt)}" ${
							value === opt ? "selected" : ""
						}>${opt}</option>`
				)
				.join("");
			return `<select ${commonAttrs}><option value="">Select ${field.label}</option>${options}</select>`;
		default:
			return `<input type="text" value="${safeValue}" ${commonAttrs}>`;
	}
}

/**
 * Escape quotes and special characters for HTML attributes
 */
function escapeQuotes(str) {
	if (!str) return "";
	return String(str)
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
		.replace(/"/g, "&quot;")
		.replace(/'/g, "&#39;")
		.replace(/\$/g, "&#36;")
		.replace(/`/g, "&#96;")
		.replace(/\{/g, "&#123;")
		.replace(/\}/g, "&#125;");
}

/**
 * Get extracted value for a field by trying different key variations
 */
function getExtractedValue(extractedData, fieldName, fieldLabel) {
	if (!extractedData || typeof extractedData !== "object") return null;

	// Try different key variations
	const keys = [
		fieldName,
		fieldLabel,
		fieldLabel.replace(/\s/g, ""),
		fieldName.replace(/_/g, " "),
		fieldName.replace(/_/g, ""),
	];

	for (const key of keys) {
		if (extractedData[key]) return extractedData[key];
		// Check case-insensitive
		const found = Object.keys(extractedData).find(
			(k) => k.toLowerCase() === key.toLowerCase()
		);
		if (found && extractedData[found]) return extractedData[found];
	}

	return null;
}

function formatExtractedText(text) {
	if (!text) return '<p class="text-muted">No text available</p>';

	// Basic formatting - preserve line breaks and add some styling
	const formattedText = text
		.replace(/\n/g, "<br>")
		.replace(/([A-Z][A-Z\s]+)/g, "<strong>$1</strong>") // Bold all caps text
		.replace(/(\d{4}-\d{2}-\d{2})/g, '<span class="text-primary">$1</span>') // Highlight dates
		.replace(/(₹[\d,]+)/g, '<span class="text-success">$1</span>') // Highlight currency
		.replace(/([A-Z]{2,3}\d{2}[A-Z]{2}\d{4})/g, '<span class="text-info">$1</span>'); // Highlight vehicle numbers

	return `<div class="extracted-text">${formattedText}</div>`;
}

function loadPDF(policyFile) {
	if (!policyFile) {
		document.getElementById("pdf-viewer").innerHTML = `
			<div class="text-center text-muted">
				<i class="fa fa-file-pdf-o fa-3x mb-3"></i>
				<p>No PDF file available</p>
			</div>
		`;
		return;
	}

	// Try to load PDF.js from CDN
	loadPDFJS(policyFile);
}

function loadPDFJS(policyFile) {
	// Check if PDF.js is already loaded
	if (window.pdfjsLib) {
		renderPDF(policyFile);
		return;
	}

	// Load PDF.js from CDN
	const script = document.createElement("script");
	script.src = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js";
	script.onload = function () {
		// Configure PDF.js worker
		window.pdfjsLib.GlobalWorkerOptions.workerSrc =
			"https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
		renderPDF(policyFile);
	};
	script.onerror = function () {
		// Fallback to iframe if PDF.js fails to load
		renderPDFFallback(policyFile);
	};
	document.head.appendChild(script);
}

function renderPDF(policyFile) {
	const pdfViewer = document.getElementById("pdf-viewer");

	// Show loading state
	pdfViewer.innerHTML = `
		<div class="text-center">
			<div class="spinner-border" role="status">
				<span class="sr-only">Loading PDF...</span>
			</div>
			<p class="mt-3">Loading PDF...</p>
		</div>
	`;

	// Get the full URL for the PDF file
	const pdfUrl = policyFile.startsWith("http")
		? policyFile
		: `${window.location.origin}${policyFile}`;

	// Load the PDF
	window.pdfjsLib
		.getDocument(pdfUrl)
		.promise.then(function (pdf) {
			// Clear loading state
			pdfViewer.innerHTML = "";

			// Create canvas for PDF rendering
			const canvas = document.createElement("canvas");
			const context = canvas.getContext("2d");
			pdfViewer.appendChild(canvas);

			// Store PDF reference for zoom controls
			window.currentPDF = pdf;
			window.currentPage = 1;
			window.currentScale = 1.0;

			// Render first page
			renderPage(pdf, 1, canvas, context);

			// Add page navigation if PDF has multiple pages
			if (pdf.numPages > 1) {
				addPageNavigation(pdf, canvas, context);
			}

			// Update zoom level display
			updateZoomDisplay();
		})
		.catch(function (error) {
			console.error("Error loading PDF:", error);
			renderPDFFallback(policyFile);
		});
}

function renderPage(pdf, pageNum, canvas, context) {
	pdf.getPage(pageNum).then(function (page) {
		const viewport = page.getViewport({ scale: window.currentScale });

		// Set canvas dimensions
		canvas.height = viewport.height;
		canvas.width = viewport.width;

		// Render the page
		const renderContext = {
			canvasContext: context,
			viewport: viewport,
		};

		page.render(renderContext);
	});
}

function addPageNavigation(pdf, canvas, context) {
	const pdfViewer = document.getElementById("pdf-viewer");

	// Create navigation controls
	const navControls = document.createElement("div");
	navControls.className = "pdf-navigation";

	navControls.innerHTML = `
		<button class="btn btn-sm btn-outline-light" id="prev-page" ${
			window.currentPage === 1 ? "disabled" : ""
		}>
			<i class="fa fa-chevron-left"></i>
		</button>
		<span id="page-info">${window.currentPage} / ${pdf.numPages}</span>
		<button class="btn btn-sm btn-outline-light" id="next-page" ${
			window.currentPage === pdf.numPages ? "disabled" : ""
		}>
			<i class="fa fa-chevron-right"></i>
		</button>
	`;

	pdfViewer.appendChild(navControls);

	// Add event listeners
	document.getElementById("prev-page").addEventListener("click", function () {
		if (window.currentPage > 1) {
			window.currentPage--;
			renderPage(pdf, window.currentPage, canvas, context);
			updatePageNavigation(pdf);
		}
	});

	document.getElementById("next-page").addEventListener("click", function () {
		if (window.currentPage < pdf.numPages) {
			window.currentPage++;
			renderPage(pdf, window.currentPage, canvas, context);
			updatePageNavigation(pdf);
		}
	});
}

function updatePageNavigation(pdf) {
	const prevBtn = document.getElementById("prev-page");
	const nextBtn = document.getElementById("next-page");
	const pageInfo = document.getElementById("page-info");

	if (prevBtn) prevBtn.disabled = window.currentPage === 1;
	if (nextBtn) nextBtn.disabled = window.currentPage === pdf.numPages;
	if (pageInfo) pageInfo.textContent = `${window.currentPage} / ${pdf.numPages}`;
}

function updateZoomDisplay() {
	const zoomLevel = document.getElementById("zoom-level");
	if (zoomLevel) {
		zoomLevel.textContent = `${Math.round(window.currentScale * 100)}%`;
	}
}

function renderPDFFallback(policyFile) {
	// Fallback to iframe if PDF.js is not available
	document.getElementById("pdf-viewer").innerHTML = `
		<div class="text-center">
			<i class="fa fa-file-pdf-o fa-3x mb-3 text-danger"></i>
			<h5>PDF Viewer</h5>
			<p class="text-muted">File: ${policyFile.split("/").pop()}</p>
			<p class="text-muted">PDF.js not available. Using fallback viewer.</p>
			<div class="pdf-fallback"><iframe src="${policyFile}" title="PDF Document"></iframe></div>
			<br><br>
			<a href="${policyFile}" target="_blank" class="btn btn-primary">
				<i class="fa fa-external-link"></i> Open PDF in New Tab
			</a>
		</div>
	`;
}

function setupEventHandlers(policyDoc, motorPolicy) {
	// Motor Policy field change handlers (auto-save)
	if (motorPolicy) {
		// Auto-save functionality
		let saveTimeout;
		const saveStatus = createSaveStatusIndicator();

		// Add change listeners to all Motor Policy fields
		document.addEventListener("change", function (e) {
			if (e.target.classList.contains("motor-policy-field")) {
				clearTimeout(saveTimeout);
				saveStatus.show("saving");

				saveTimeout = setTimeout(() => {
					saveMotorPolicyField(
						motorPolicy.name,
						e.target.dataset.fieldname,
						e.target.value,
						saveStatus
					);
				}, 500); // Debounce saves by 500ms
			}
		});

		// Handle copy extracted value buttons
		window.copyExtractedValue = function (fieldName, extractedValue) {
			const field = document.getElementById(`field-${fieldName}`);
			if (field) {
				field.value = extractedValue;
				field.dispatchEvent(new Event("change")); // Trigger save
				frappe.show_alert({ message: "Value copied!", indicator: "green" });
			}
		};

		// Handle copy from button data attributes (safer approach)
		window.copyExtractedValueFromButton = function (button) {
			const fieldName = button.getAttribute("data-field");
			const extractedValue = button.getAttribute("data-value");
			const field = document.getElementById(`field-${fieldName}`);
			if (field && extractedValue) {
				field.value = extractedValue;
				field.dispatchEvent(new Event("change")); // Trigger save
				frappe.show_alert({ message: "Value copied!", indicator: "green" });
			}
		};

		// Handle save all button
		const saveBtn = document.getElementById("save-policy");
		if (saveBtn) {
			saveBtn.addEventListener("click", function () {
				saveAllMotorPolicyChanges(motorPolicy.name, saveStatus);
			});
		}

		// Handle refresh button
		const refreshBtn = document.getElementById("refresh-policy");
		if (refreshBtn) {
			refreshBtn.addEventListener("click", function () {
				// Reset button appearance if it was showing warning state
				this.classList.remove("btn-warning");
				this.classList.add("btn-outline-info");
				this.innerHTML = '<i class="fa fa-refresh"></i> Refresh';

				// Reload the page with same parameters to get fresh data
				window.location.reload();
			});
		}

		// Handle toggle extracted fields button
		const toggleBtn = document.getElementById("toggle-extracted");
		if (toggleBtn) {
			toggleBtn.addEventListener("click", function () {
				const content = document.getElementById("policy-fields-content");
				if (this.textContent === "Show Extracted") {
					content.innerHTML = formatExtractedFields(policyDoc);
					this.textContent = "Show Form Fields";
					this.classList.remove("btn-outline-secondary");
					this.classList.add("btn-outline-primary");
				} else {
					content.innerHTML = renderMotorPolicyFields(motorPolicy, policyDoc);
					this.textContent = "Show Extracted";
					this.classList.remove("btn-outline-primary");
					this.classList.add("btn-outline-secondary");
					// Re-attach event listeners after re-rendering
					setupMotorPolicyFieldListeners(motorPolicy.name, saveStatus);
				}
			});
		}
	}

	// Resize handle functionality
	const container = document.querySelector(".policy-viewer-container");
	const resizeHandle = document.querySelector(".resize-handle");
	const pdfPane = document.querySelector(".pdf-pane");
	const fieldsPane = document.querySelector(".fields-pane");

	let isResizing = false;

	resizeHandle.addEventListener("mousedown", function (e) {
		isResizing = true;
		document.body.style.cursor = "col-resize";
		document.body.style.userSelect = "none";
	});

	document.addEventListener("mousemove", function (e) {
		if (!isResizing) return;

		const containerRect = container.getBoundingClientRect();
		const newPdfWidth = e.clientX - containerRect.left;
		const containerWidth = containerRect.width;

		if (newPdfWidth > 200 && newPdfWidth < containerWidth - 200) {
			const pdfPercentage = (newPdfWidth / containerWidth) * 100;
			pdfPane.style.flex = `0 0 ${pdfPercentage}%`;
			fieldsPane.style.flex = `0 0 ${100 - pdfPercentage}%`;
		}
	});

	document.addEventListener("mouseup", function () {
		if (isResizing) {
			isResizing = false;
			document.body.style.cursor = "";
			document.body.style.userSelect = "";
		}
	});

	// Toggle view functionality (between fields and raw text) - only if element exists
	const toggleViewBtn = document.getElementById("toggle-view");
	if (toggleViewBtn) {
		toggleViewBtn.addEventListener("click", function () {
			const button = this;
			const content = document.getElementById("extracted-fields-content");
			const container = document.querySelector(".fields-container");

			if (button.textContent === "Show Raw Text") {
				// Switch to raw text view
				content.innerHTML = policyDoc.raw_ocr_text
					? formatExtractedText(policyDoc.raw_ocr_text)
					: '<p class="text-muted">No raw text available</p>';
				button.textContent = "Show Extracted Fields";
				button.classList.remove("btn-outline-secondary");
				button.classList.add("btn-outline-primary");
			} else {
				// Switch to fields view
				content.innerHTML = formatExtractedFields(policyDoc);
				button.textContent = "Show Raw Text";
				button.classList.remove("btn-outline-primary");
				button.classList.add("btn-outline-secondary");
			}
		});
	}

	// Copy fields functionality - only if element exists
	const copyFieldsBtn = document.getElementById("copy-fields");
	if (copyFieldsBtn) {
		copyFieldsBtn.addEventListener("click", function () {
			const content = document.getElementById("extracted-fields-content");
			let textToCopy = "";

			// Check if we're showing fields or raw text
			const tableRows = content.querySelectorAll("table tbody tr");
			if (tableRows.length > 0) {
				// Copy table data as text
				tableRows.forEach((row) => {
					const cells = row.querySelectorAll("td");
					if (cells.length >= 2) {
						const label = cells[0].textContent.trim();
						const value = cells[1].textContent.trim();
						textToCopy += `${label}: ${value}\n`;
					}
				});
			} else {
				// Copy raw text
				textToCopy = content.textContent.trim();
			}

			navigator.clipboard.writeText(textToCopy).then(function () {
				frappe.show_alert({
					message: "Content copied to clipboard!",
					indicator: "green",
				});
			});
		});
	}

	// Zoom controls - only if elements exist
	const zoomInBtn = document.getElementById("zoom-in");
	if (zoomInBtn) {
		zoomInBtn.addEventListener("click", function () {
			if (window.currentPDF && window.currentScale < 3.0) {
				window.currentScale += 0.25;
				const canvas = document.querySelector("#pdf-viewer canvas");
				if (canvas) {
					const context = canvas.getContext("2d");
					renderPage(window.currentPDF, window.currentPage, canvas, context);
					updateZoomDisplay();
				}
			}
		});
	}

	const zoomOutBtn = document.getElementById("zoom-out");
	if (zoomOutBtn) {
		zoomOutBtn.addEventListener("click", function () {
			if (window.currentPDF && window.currentScale > 0.5) {
				window.currentScale -= 0.25;
				const canvas = document.querySelector("#pdf-viewer canvas");
				if (canvas) {
					const context = canvas.getContext("2d");
					renderPage(window.currentPDF, window.currentPage, canvas, context);
					updateZoomDisplay();
				}
			}
		});
	}
}

/**
 * Create save status indicator
 */
function createSaveStatusIndicator() {
	// Create status element if it doesn't exist
	let statusEl = document.getElementById("save-status");
	if (!statusEl) {
		statusEl = document.createElement("div");
		statusEl.id = "save-status";
		document.body.appendChild(statusEl);
	}

	return {
		show: function (type) {
			const messages = {
				saving: { text: "Saving...", class: "bg-warning text-dark" },
				saved: { text: "Saved!", class: "bg-success text-white" },
				error: { text: "Save failed", class: "bg-danger text-white" },
			};

			const msg = messages[type] || messages.error;
			statusEl.textContent = msg.text;
			statusEl.className = msg.class;
			statusEl.style.display = "block";

			if (type === "saved") {
				setTimeout(() => (statusEl.style.display = "none"), 2000);
			}
		},
		hide: function () {
			statusEl.style.display = "none";
		},
	};
}

/**
 * Save individual Motor Policy field with version conflict handling
 */
function saveMotorPolicyField(motorPolicyName, fieldName, value, saveStatus) {
	// First get the latest document version
	frappe.call({
		method: "frappe.client.get",
		args: {
			doctype: "Motor Policy",
			name: motorPolicyName,
		},
		callback: function (response) {
			if (response.message) {
				const latestDoc = response.message;

				// Update the specific field with our value
				latestDoc[fieldName] = value;

				// Save the updated document
				frappe.call({
					method: "frappe.client.save",
					args: {
						doc: latestDoc,
					},
					callback: function (saveResponse) {
						if (saveResponse.message) {
							saveStatus.show("saved");

							// Update the form field with any server-side modifications
							const field = document.getElementById(`field-${fieldName}`);
							if (field && saveResponse.message[fieldName] !== undefined) {
								field.value = saveResponse.message[fieldName];
							}
						} else {
							saveStatus.show("error");
						}
					},
					error: function (err) {
						console.error("Save error:", err);
						handleSaveError(err, saveStatus);
					},
				});
			}
		},
		error: function (err) {
			console.error("Fetch latest document error:", err);
			saveStatus.show("error");
			frappe.show_alert({
				message: "Failed to fetch latest document. Please refresh the page.",
				indicator: "red",
			});
		},
	});
}

/**
 * Handle save errors with appropriate user feedback
 */
function handleSaveError(err, saveStatus) {
	saveStatus.show("error");

	if (err.message) {
		if (err.message.includes("has been modified")) {
			frappe.show_alert({
				message: "Document was modified. Please refresh to get the latest version.",
				indicator: "orange",
			});

			// Add a refresh button to the fields pane header if it doesn't exist
			const refreshBtn = document.getElementById("refresh-policy");
			if (refreshBtn) {
				refreshBtn.classList.add("btn-warning");
				refreshBtn.innerHTML = '<i class="fa fa-refresh"></i> Refresh Required';
			}
		} else if (err.message.includes("Permission")) {
			frappe.show_alert({
				message: "You do not have permission to modify this document.",
				indicator: "red",
			});
		} else {
			frappe.show_alert({
				message: `Save failed: ${err.message}`,
				indicator: "red",
			});
		}
	} else {
		frappe.show_alert({
			message: "Save failed due to an unknown error",
			indicator: "red",
		});
	}
}

/**
 * Save all Motor Policy changes at once with improved error handling
 */
function saveAllMotorPolicyChanges(motorPolicyName, saveStatus) {
	const fields = document.querySelectorAll(".motor-policy-field");
	const updates = {};

	// Collect all field values
	fields.forEach((field) => {
		updates[field.dataset.fieldname] = field.value;
	});

	saveStatus.show("saving");

	// Get the latest document version first
	frappe.call({
		method: "frappe.client.get",
		args: {
			doctype: "Motor Policy",
			name: motorPolicyName,
		},
		callback: function (response) {
			if (response.message) {
				const latestDoc = response.message;

				// Merge updates with the latest document
				Object.keys(updates).forEach((fieldName) => {
					latestDoc[fieldName] = updates[fieldName];
				});

				// Save the updated document
				frappe.call({
					method: "frappe.client.save",
					args: {
						doc: latestDoc,
					},
					callback: function (saveResponse) {
						if (saveResponse.message) {
							saveStatus.show("saved");
							frappe.show_alert({
								message: "All changes saved successfully!",
								indicator: "green",
							});

							// Update form fields with any server-side modifications
							updateFormFieldsFromDocument(saveResponse.message);
						} else {
							saveStatus.show("error");
							frappe.show_alert({
								message: "Save failed - no response from server",
								indicator: "red",
							});
						}
					},
					error: function (err) {
						console.error("Save all error:", err);
						handleSaveError(err, saveStatus);
					},
				});
			}
		},
		error: function (err) {
			console.error("Fetch document error:", err);
			saveStatus.show("error");
			frappe.show_alert({
				message: "Failed to fetch latest document. Please refresh the page.",
				indicator: "red",
			});
		},
	});
}

/**
 * Update form fields with values from saved document
 */
function updateFormFieldsFromDocument(doc) {
	document.querySelectorAll(".motor-policy-field").forEach((field) => {
		const fieldName = field.dataset.fieldname;
		if (doc[fieldName] !== undefined) {
			field.value = doc[fieldName] || "";
		}
	});
}
