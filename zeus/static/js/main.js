/* System-wide event handlers shared across zeus apps */

import { formatTimeStampElement, formatTimeStampValue } from "./utils/time_utils.js";

function htmxAlert(alert) {
    const alertDiv = document.getElementById("alert-container")
    alertDiv.innerHTML = `
    <div class="alert alert-dismissible alert-${alert.severity || 'danger'} alert-float">
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        ${alert.message || "Oof. Unknown Error Occurred."}
    </div>`
}

// Replace <select> elements that include the provided selectors with Choices instance
function initChoices(selectors) {
    document.querySelectorAll(selectors).forEach(el => {
        new Choices(el, {
                removeItemButton: true,
                duplicateItemsAllowed: false,
                searchFields: ['label'],
                position: 'bottom',
                allowHTML: false,
            }
        )
    })
}

// Replace innerText of elements that match the provided selectors with a dayjs-formatted value
function initTimeStamps(selectors) {
    document.querySelectorAll(selectors).forEach(el =>{
        formatTimeStampElement(el)
    })

}

// Add event handlers and process elements on page load
// Uses `htmx.onLoad` instead of `window.addEventListener` because it will fire on normal page loads
// and htmx responses
htmx.onLoad(function() {
    initChoices('.js-choices')
    initTimeStamps('[data-timestamp]')

})

// Flash error upon unhandled htmx response error
htmx.on("htmx:responseError", function(evt) {
    htmxAlert({})
})

export {formatTimeStampValue}
