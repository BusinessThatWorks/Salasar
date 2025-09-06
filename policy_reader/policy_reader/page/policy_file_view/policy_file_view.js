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
		<div class="policy-viewer-container" style="height: calc(100vh - 120px); display: flex; border: 1px solid #d1d5db;">
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

			<!-- Text Viewer Pane -->
			<div class="text-pane" style="flex: 1; min-width: 0; position: relative;">
				<div class="pane-header" style="background: #f8f9fa; padding: 10px 15px; border-bottom: 1px solid #d1d5db; display: flex; justify-content: space-between; align-items: center;">
					<h5 class="mb-0">Extracted Text</h5>
					<div class="text-controls">
						<button class="btn btn-sm btn-outline-secondary" id="search-text">Search</button>
						<button class="btn btn-sm btn-outline-secondary" id="copy-text">Copy</button>
					</div>
				</div>
				<div class="text-container" style="height: calc(100% - 50px); overflow: auto; padding: 15px; background: white;">
					<div id="extracted-text-content">
						${
							policyDoc.raw_ocr_text
								? formatExtractedText(policyDoc.raw_ocr_text)
								: '<p class="text-muted">No extracted text available</p>'
						}
					</div>
				</div>
			</div>
		</div>

		<!-- Search Modal -->
		<div class="modal fade" id="searchModal" tabindex="-1" role="dialog">
			<div class="modal-dialog" role="document">
				<div class="modal-content">
					<div class="modal-header">
						<h5 class="modal-title">Search in Text</h5>
						<button type="button" class="close" data-dismiss="modal">
							<span>&times;</span>
						</button>
					</div>
					<div class="modal-body">
						<input type="text" class="form-control" id="search-input" placeholder="Enter search term...">
					</div>
					<div class="modal-footer">
						<button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
						<button type="button" class="btn btn-primary" id="search-btn">Search</button>
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
	const textPane = document.querySelector(".text-pane");

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
			textPane.style.flex = `0 0 ${100 - pdfPercentage}%`;
		}
	});

	document.addEventListener("mouseup", function () {
		if (isResizing) {
			isResizing = false;
			document.body.style.cursor = "";
			document.body.style.userSelect = "";
		}
	});

	// Search functionality
	document.getElementById("search-text").addEventListener("click", function () {
		$("#searchModal").modal("show");
	});

	document.getElementById("search-btn").addEventListener("click", function () {
		const searchTerm = document.getElementById("search-input").value;
		if (searchTerm) {
			searchInText(searchTerm);
			$("#searchModal").modal("hide");
		}
	});

	// Copy text functionality
	document.getElementById("copy-text").addEventListener("click", function () {
		const textContent = document.getElementById("extracted-text-content").textContent;
		navigator.clipboard.writeText(textContent).then(function () {
			frappe.show_alert({
				message: "Text copied to clipboard!",
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

function searchInText(searchTerm) {
	const textContent = document.getElementById("extracted-text-content");
	const originalHTML = textContent.innerHTML;

	// Remove previous highlights
	const cleanText = textContent.textContent;

	// Create highlighted version
	const highlightedText = cleanText.replace(
		new RegExp(searchTerm, "gi"),
		`<mark style="background-color: yellow; padding: 2px 4px;">$&</mark>`
	);

	textContent.innerHTML = highlightedText;

	// Scroll to first match
	const firstMatch = textContent.querySelector("mark");
	if (firstMatch) {
		firstMatch.scrollIntoView({ behavior: "smooth", block: "center" });
	}

	// Show search results count
	const matches = textContent.querySelectorAll("mark");
	frappe.show_alert({
		message: `Found ${matches.length} matches for "${searchTerm}"`,
		indicator: "blue",
	});
}
