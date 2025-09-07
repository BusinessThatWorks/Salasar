frappe.pages["policy-file-view"].on_page_load = function (wrapper) {

	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Policy Viewer",
		single_column: true,
	});

	// Get policy document ID from URL parameters
	const urlParams = new URLSearchParams(window.location.search);
	const policyDocumentId = urlParams.get("policy_document");

	if (!policyDocumentId) {
		page.main.html(`
			<div class="text-center" style="padding: 50px;">
				<h3>No Policy Document Selected</h3>
				<p>Please select a policy document to view.</p>
			</div>
		`);
		return;
	}

	// Load policy document data and render split pane
	loadPolicyDocument(page, policyDocumentId);

};

function loadPolicyDocument(page, policyDocumentId) {
	// Show loading state
	page.main.html(`
		<div class="text-center" style="padding: 50px;">
			<div class="spinner-border" role="status">
				<span class="sr-only">Loading...</span>
			</div>
			<p class="mt-3">Loading policy document...</p>
		</div>
	`);

	// Fetch policy document data
	frappe.call({
		method: "frappe.client.get",
		args: {
			doctype: "Policy Document",
			name: policyDocumentId,
		},
		callback: function (r) {
			if (r.message) {
				renderSplitPane(page, r.message);
			} else {
				page.main.html(`
					<div class="text-center" style="padding: 50px;">
						<h3>Error Loading Document</h3>
						<p>Could not load policy document: ${policyDocumentId}</p>
					</div>
				`);
			}
		},
		error: function (err) {
			page.main.html(`
				<div class="text-center" style="padding: 50px;">
					<h3>Error Loading Document</h3>
					<p>Failed to load policy document: ${err.message || "Unknown error"}</p>
				</div>
			`);
		},
	});
}

function renderSplitPane(page, policyDoc) {
	// Create split pane layout
	page.main.html(`
		<!-- Header with Policy Document Link -->
		<div class="policy-header" style="background: #f8f9fa; padding: 15px; border-bottom: 1px solid #d1d5db; margin-bottom: 0;">
			<div class="d-flex justify-content-between align-items-center">
				<div>
					<div class="d-flex align-items-center mb-2">
						<button class="btn btn-outline-secondary btn-sm mr-3" onclick="window.close()" title="Close this tab">
							<i class="fa fa-times"></i> Close
						</button>
						<button class="btn btn-outline-info btn-sm mr-3" onclick="restoreNavigation(); window.location.href='/app'" title="Back to Frappe">
							<i class="fa fa-home"></i> Back to Frappe
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

		<div class="policy-viewer-container" style="height: calc(100vh - 180px); display: flex; border: 1px solid #d1d5db;">
			<!-- PDF Viewer Pane -->
			<div class="pdf-pane" style="flex: 1; min-width: 0; border-right: 1px solid #d1d5db; position: relative;">
				<div class="pane-header" style="background: #f8f9fa; padding: 10px 15px; border-bottom: 1px solid #d1d5db; display: flex; justify-content: space-between; align-items: center;">
					<h5 class="mb-0">PDF Document</h5>
					<div class="pdf-controls">
						<button class="btn btn-sm btn-outline-secondary" id="zoom-out">-</button>
						<span id="zoom-level" class="mx-2">100%</span>
						<button class="btn btn-sm btn-outline-secondary" id="zoom-in">+</button>
					</div>
				</div>
				<div class="pdf-container" style="height: calc(100% - 50px); overflow: auto; background: #f5f5f5;">
					<div id="pdf-viewer" style="width: 100%; height: 100%; display: flex; justify-content: center; align-items: center;">
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
			<div class="resize-handle" style="width: 8px; background: #e5e7eb; cursor: col-resize; position: relative;" title="Drag to resize">
				<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 2px; height: 30px; background: #9ca3af;"></div>
			</div>

			<!-- Extracted Fields Pane -->
			<div class="fields-pane" style="flex: 1; min-width: 0; position: relative;">
				<div class="pane-header" style="background: #f8f9fa; padding: 10px 15px; border-bottom: 1px solid #d1d5db; display: flex; justify-content: space-between; align-items: center;">
					<h5 class="mb-0">Extracted Fields</h5>
					<div class="fields-controls">
						<button class="btn btn-sm btn-outline-secondary" id="toggle-view">Show Raw Text</button>
						<button class="btn btn-sm btn-outline-secondary" id="copy-fields">Copy</button>
					</div>
				</div>
				<div class="fields-container" style="height: calc(100% - 50px); overflow: auto; padding: 15px; background: white;">
					<div id="extracted-fields-content">
						${formatExtractedFields(policyDoc)}
					</div>
				</div>
			</div>
		</div>

	`);

	// Load PDF
	loadPDF(policyDoc.policy_file);

	// Setup event handlers
	setupEventHandlers(policyDoc);
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
			<div class="text-center text-muted" style="padding: 40px;">
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
				<div class="text-center text-muted" style="padding: 40px;">
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

	// Create table structure
	html += `
		<div class="fields-table-section">
			<div class="table-header" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 12px 20px; border-radius: 8px 8px 0 0; margin-bottom: 0;">
				<h5 class="mb-0" style="font-weight: 600;">
					<i class="fa fa-list"></i> Extracted Fields
				</h5>
			</div>
			<div class="table-content" style="background: white; border: 1px solid #e9ecef; border-top: none; border-radius: 0 0 8px 8px; overflow: hidden;">
				<div class="table-responsive">
					<table class="table table-hover mb-0">
						<tbody>
	`;

	// Render fields from data (handles both flat and nested structures)
	html += renderDataRows(extractedData);

	html += `
						</tbody>
					</table>
				</div>
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
function renderDataRows(data, prefix = '') {
	let html = '';
	
	Object.keys(data).forEach((key) => {
		const value = data[key];
		const displayKey = prefix ? `${prefix} > ${key}` : key;

		if (value && typeof value === 'object' && !Array.isArray(value)) {
			// Nested object - render with prefix
			html += renderDataRows(value, displayKey);
		} else {
			// Simple key-value pair
			html += `
				<tr style="border-bottom: 1px solid #f8f9fa;">
					<td style="width: 40%; padding: 12px 20px; font-weight: 600; color: #495057; background: #f8f9fa; border-right: 1px solid #e9ecef;">
						${formatFieldLabel(displayKey)}
					</td>
					<td style="width: 60%; padding: 12px 20px; color: #212529;">
						${formatFieldValue(value)}
					</td>
				</tr>
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
	if (!value || value === "null" || value === "undefined" || value === "None" || value === null || value === undefined) {
		return '<span class="text-muted"><i class="fa fa-minus"></i> Not available</span>';
	}

	// Convert to string for processing
	const stringValue = String(value).trim();

	// Handle empty strings
	if (stringValue === "" || stringValue === "None") {
		return '<span class="text-muted"><i class="fa fa-minus"></i> Not available</span>';
	}

	// Format dates (basic patterns)
	if (typeof value === "string" && (/^\d{4}-\d{2}-\d{2}$/.test(stringValue) || /^\d{1,2}\/\d{1,2}\/\d{4}$/.test(stringValue))) {
		return `<span class="text-primary"><i class="fa fa-calendar"></i> ${stringValue}</span>`;
	}

	// Format currency amounts
	if ((typeof value === "number" && value > 0) || (typeof value === "string" && /^₹?[\d,]+/.test(stringValue))) {
		return `<span class="text-success"><i class="fa fa-rupee"></i> ${stringValue}</span>`;
	}

	// Default formatting for regular text
	return `<span class="text-dark">${stringValue}</span>`;
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
	navControls.style.cssText = `
		position: absolute;
		bottom: 10px;
		left: 50%;
		transform: translateX(-50%);
		background: rgba(0,0,0,0.7);
		color: white;
		padding: 8px 15px;
		border-radius: 20px;
		display: flex;
		align-items: center;
		gap: 10px;
		z-index: 10;
	`;

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
			<iframe src="${policyFile}" style="width: 100%; height: 500px; border: none;" title="PDF Document"></iframe>
			<br><br>
			<a href="${policyFile}" target="_blank" class="btn btn-primary">
				<i class="fa fa-external-link"></i> Open PDF in New Tab
			</a>
		</div>
	`;
}

function setupEventHandlers(policyDoc) {
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

	// Toggle view functionality (between fields and raw text)
	document.getElementById("toggle-view").addEventListener("click", function () {
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

	// Copy fields functionality
	document.getElementById("copy-fields").addEventListener("click", function () {
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

	// Zoom controls
	document.getElementById("zoom-in").addEventListener("click", function () {
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

	document.getElementById("zoom-out").addEventListener("click", function () {
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
