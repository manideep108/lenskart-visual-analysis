// Rate Limit Error Handling for Lenskart Visual Measurement System

// Global variables for countdown state
let countdownInterval = null;
let lastFormData = null;

/**
 * Display the rate limit banner with countdown timer and suggestions
 */
function showRateLimitBanner(data) {
    const banner = document.getElementById('rateLimitBanner');
    const message = document.getElementById('rateLimitMessage');
    const suggestionsList = document.getElementById('rateLimitSuggestions');

    banner.classList.remove('hidden');
    message.textContent = data.error_message || 'API quota exceeded. Please wait before retrying.';

    // Populate suggestions list
    suggestionsList.innerHTML = '';
    if (data.rate_limit_info && data.rate_limit_info.suggestions) {
        data.rate_limit_info.suggestions.forEach(suggestion => {
            const li = document.createElement('li');
            li.className = 'flex items-start gap-2';
            li.innerHTML = `<span class="text-amber-600">•</span><span>${suggestion}</span>`;
            suggestionsList.appendChild(li);
        });

        // Add rate limit details
        const detailsLi = document.createElement('li');
        detailsLi.className = 'flex items-start gap-2 mt-2 pt-2 border-t border-amber-200';
        detailsLi.innerHTML = `<span class="text-amber-600">ℹ️</span><span><strong>Limit:</strong> ${data.rate_limit_info.limit} | <strong>Reset:</strong> ${data.rate_limit_info.reset_time}</span>`;
        suggestionsList.appendChild(detailsLi);
    }

    // Start countdown timer if retry delay is provided
    if (data.retry_after_seconds) {
        startCountdown(data.retry_after_seconds);
    }

    // Scroll banner into view
    banner.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

/**
 * Start countdown timer with progress bar
 */
function startCountdown(seconds) {
    const timerDisplay = document.getElementById('countdownTimer');
    const progressBar = document.getElementById('countdownBar');
    const retryButton = document.getElementById('retryButton');

    let remaining = seconds;
    const total = seconds;

    // Clear any existing countdown
    if (countdownInterval) {
        clearInterval(countdownInterval);
    }

    // Disable retry button initially
    retryButton.disabled = true;
    retryButton.textContent = '🔄 Retry Now';

    // Update display helper function
    const updateDisplay = () => {
        const minutes = Math.floor(remaining / 60);
        const secs = remaining % 60;
        timerDisplay.textContent = `${minutes}:${secs.toString().padStart(2, '0')}`;
        progressBar.style.width = `${(remaining / total) * 100}%`;
    };

    // Update immediately
    updateDisplay();

    // Start interval
    countdownInterval = setInterval(() => {
        remaining--;

        if (remaining <= 0) {
            clearInterval(countdownInterval);
            timerDisplay.textContent = 'Ready!';
            progressBar.style.width = '0%';
            retryButton.disabled = false;
            retryButton.textContent = '✅ Retry Now';
        } else {
            updateDisplay();
        }
    }, 1000);
}

/**
 * Dismiss the rate limit banner and clear countdown
 */
function dismissRateLimitBanner() {
    document.getElementById('rateLimitBanner').classList.add('hidden');
    if (countdownInterval) {
        clearInterval(countdownInterval);
        countdownInterval = null;
    }
}

/**
 * Load and display demo data using user's actual input
 */
async function loadDemoData() {
    try {
        // Get user's input from the form
        const productIdInput = document.getElementById('productId');
        const imageUrlsInput = document.getElementById('imageUrls');

        if (!productIdInput || !imageUrlsInput) {
            throw new Error('Form inputs not found');
        }

        const productId = productIdInput.value.trim() || 'DEMO-PRODUCT';
        const imageUrlsText = imageUrlsInput.value.trim();

        // Parse image URLs (split by newlines and filter empty lines)
        const imageUrls = imageUrlsText
            .split('\n')
            .map(url => url.trim())
            .filter(url => url.length > 0);

        const imageCount = imageUrls.length || 1;

        // Get stored rate limit response (if exists)
        const rateLimitResponse = window.lastRateLimitResponse || {};

        // Use REAL validation if available, otherwise fake it
        let imageValidation;
        let validUrls = imageUrls;  // Assume all valid by default

        if (rateLimitResponse.image_validation) {
            // Use REAL validation data from backend
            imageValidation = rateLimitResponse.image_validation;

            // Filter to only valid URLs for generating demo analysis
            const invalidUrlSet = new Set(
                (imageValidation.invalid_urls || []).map(inv => inv.url)
            );
            validUrls = imageUrls.filter(url => !invalidUrlSet.has(url));
        } else {
            // Fall back to fake "all valid" data
            imageValidation = {
                total_provided: imageCount,
                valid_count: imageCount,
                invalid_count: 0,
                invalid_urls: []
            };
        }

        // Generate per_image_analysis for VALID URLs only with slightly different scores
        const perImageAnalysis = validUrls.map((url, index) => {
            const variation = (index * 0.05); // Slight variation for each image
            return {
                "image_url": url,
                "measurements": {
                    "frame_shape": "rectangular",
                    "frame_material": "acetate",
                    "lens_color": "transparent",
                    "frame_color": "black",
                    "temple_style": "standard",
                    "nose_bridge_type": "keyhole"
                },
                "confidence_scores": {
                    "frame_shape": Math.min(0.95 - variation, 1.0),
                    "frame_material": Math.min(0.88 + variation, 1.0),
                    "lens_color": Math.min(0.92 - variation * 0.5, 1.0),
                    "frame_color": Math.min(0.90 + variation * 0.8, 1.0),
                    "temple_style": Math.min(0.85 - variation * 0.3, 1.0),
                    "nose_bridge_type": Math.min(0.80 + variation * 1.2, 1.0)
                }
            };
        });

        // If no valid URLs, generate one demo entry
        if (perImageAnalysis.length === 0) {
            perImageAnalysis.push({
                "image_url": "demo_image_url",
                "measurements": {
                    "frame_shape": "rectangular",
                    "frame_material": "acetate",
                    "lens_color": "transparent",
                    "frame_color": "black",
                    "temple_style": "standard",
                    "nose_bridge_type": "keyhole"
                },
                "confidence_scores": {
                    "frame_shape": 0.95,
                    "frame_material": 0.88,
                    "lens_color": 0.92,
                    "frame_color": 0.90,
                    "temple_style": 0.85,
                    "nose_bridge_type": 0.80
                }
            });
        }

        // Construct demo response with user's actual input
        const demoData = {
            "status": "success",
            "product_id": productId,
            "total_images_provided": imageCount,
            "images_successfully_analyzed": validUrls.length,  // Only count valid images
            "per_image_analysis": perImageAnalysis,
            "image_validation": imageValidation,  // Include validation data
            "aggregated_measurements": {
                "frame_shape": "rectangular",
                "frame_material": "acetate",
                "lens_color": "transparent",
                "frame_color": "black",
                "temple_style": "standard",
                "nose_bridge_type": "keyhole"
            },
            "overall_confidence": 0.88,
            "notes": "⚠️ DEMO MODE: This is simulated data using your input. Scores are fake for demonstration purposes."
        };

        // Call the main displayResults function (defined in index.html)
        if (typeof displayResults === 'function') {
            displayResults(demoData);
            dismissRateLimitBanner();
        } else {
            console.error('displayResults function not found');
            alert('Error: Main display function not available');
        }
    } catch (error) {
        console.error('Failed to generate demo data:', error);
        alert('Could not generate demo data. Please check your form inputs.');
    }
}

/**
 * Retry the last analysis request
 */
function retryAnalysis() {
    if (window.lastFormData) {
        // Populate form fields with saved data
        document.getElementById('productId').value = window.lastFormData.productId;

        // Handle imageUrls - it's already an array
        const imageUrlsTextarea = document.getElementById('imageUrls');
        if (Array.isArray(window.lastFormData.imageUrls)) {
            imageUrlsTextarea.value = window.lastFormData.imageUrls.join('\n');
        } else {
            imageUrlsTextarea.value = window.lastFormData.imageUrls;
        }

        dismissRateLimitBanner();

        // Trigger the analyze button click
        const analyzeBtn = document.getElementById('analyzeBtn');
        if (analyzeBtn) {
            analyzeBtn.click();
        }
    } else {
        alert('No previous request to retry');
    }
}
