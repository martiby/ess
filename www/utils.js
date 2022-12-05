



/**
 * Check if a variable is a number.
 *
 * @param value
 * @returns {boolean}
 */
function is_number(value) {
    return ((typeof (value) === 'number'));
}


/**
 * Fetch JSON (AJAX Request)
 *
 * @param url requested url
 * @param success callback for success
 * @param error callback for error (optional)
 * @param post dictionary to send as json post (optional)
 */
function fetch_json(url, success, error, post) {

    if (post) {
        post = {
            method: 'POST',
            body: JSON.stringify(post),
            headers: {'Content-Type': 'application/json'}
        }
    }

    fetch(url, post).then(function (response) {
        if (response.ok) {
            return response.json();
        } else {
            return Promise.reject(response);
        }
    }).then(function (data) {
        success(data);
    }).catch(function (err) {
        if (error) error(err);
    });
}


/**
 * Format float or integer with --- as default.
 *
 * Example usage:  document.getElementById('value1').textContent = fmtNumber(data.x.y ?? null, 2) + ' A';
 * @param value  float or integer
 * @param precision  number of digits displayed after the decimal point
 * @returns {string}
 */
fmtNumber = function (value, precision) {
    try {
        if (isNaN(value)) throw true;
        return value.toFixed(precision);
    } catch (e) {
        return (precision) ? '-.' + '-'.repeat(precision) : "---";
    }
};
