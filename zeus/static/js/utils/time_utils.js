import '../lib/dayjs1.11.5.min.js'
import '../lib/dayjs_utc1.11.5.js'

dayjs.extend(window.dayjs_plugin_utc)

const DEFAULT_FORMAT = "MM/DD/YY hh:mm:ss a"

export const formatTimeStampElement = function(el) {
    // Use dayjs to format the element's innerText based on data attributes
    // Element is expected to have a `data-timestamp` attribute set to a valid unix timestamp
    // or a value that evaluates false if field should be blank
    // The format can optionally be set as the `data-timeformat` attribute
    if (el.dataset.timestamp) {
        const fmt = el.dataset.timeformat || DEFAULT_FORMAT
        const formatted = formatTimeStampValue(el.dataset.timestamp, fmt)

        if (formatted) {
            el.innerText = formatted
        }
    }
}

export const formatTimeStampValue = function(value, format = undefined) {
    // Use dayjs to format the value provided using the format provided
    if (value) {
        const fmt = format || DEFAULT_FORMAT

        // Parse timestamp into  dayjs object and set timezone to utc
        // const parsed = dayjs.unix(value).utc(true)
        const parsed = dayjs.unix(value)

        if (dayjs(parsed).isValid()) {
            // Convert to browser-local timezone and apply format then set as innerText
            return parsed.local().format(fmt)
        }
    }
    return ''


}
