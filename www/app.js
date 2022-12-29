var app = app || {};

/**
 * Helper for a short document.getElementById()
 *
 * @param id
 * @returns {HTMLElement}
 */
$id = function (id) {
    return document.getElementById(id);
}

app.init = function () {
    var self = app;
    console.log("app.init");

    self.manual_cmd = null;

    // Setup PowerFlow view (https://github.com/martiby/PowerFlow)
    // {id: 'car', type: 'car', sign: -1, wallbox: true}],
    const pflow_config = {
        table: [
            {id: 'pv', type: 'pv'},
            {id: 'home', type: 'home', sign: -1},
            {id: 'bat', type: 'bat', sign: -1},
            {id: 'grid', type: 'grid'} ],
        bar: {
            in: [
                {id: 'pv', type: 'pv'},
                {id: 'bat', type: 'bat', sign: -1},
                {id: 'grid', type: 'grid'}],
            out: [
                {id: 'home', type: 'home'},
                {id: 'car', type: 'car'},
                {id: 'heat', type: 'heat'},
                {id: 'bat', type: 'bat'},
                {id: 'grid', type: 'grid', sign: -1}]
        }
    };

    if(config_enable_heat) {
        pflow_config.table.push({id: 'heat', type: 'heat', sign: -1});

    }

    if(config_enable_car) {
        pflow_config.table.push({id: 'car', type: 'car', sign: -1, wallbox: true});
    }

    app.pflow = new Pflow('pflow-table', 'pflow-bar', pflow_config);  // Init PowerFlow


    // event for info logo to toggle detail information

    $id('info-logo').addEventListener('click', function () {
        let ele = $id('container-detail');
        if (ele.style.display === "none") {
            ele.style.display = "block";
            $id('pflow-table').style.display = 'none';
        } else {
            ele.style.display = "none";
            $id('pflow-table').style.display = 'block';
        }
    });

    // event for option dropdown (std, chg_boost, feed_boost)

    ['change', 'tap'].forEach(evt =>
        $id('option-select').addEventListener(evt, function () {
            let post = {'option': $id('option-select').value};
            console.log("set option", post);
            fetch_json('api/set', self.show_state, null, post);
        }, false)
    );

    // event for mode buttons

    document.querySelectorAll("[data-mode]").forEach(button => {
        button.addEventListener("click", (evt) => {
            let mode = button.getAttribute('data-mode');
            fetch_json('api/set', self.show_state, null, {'mode': mode});
        })
    });

    $id('btn-error-reset').addEventListener('click', function () {
        fetch_json('api/set', self.show_state, null, {'reset_error': true});
    });

    $id('manual-charge-slider').addEventListener('input', function (evt) {
        $id('manual-charge-info').textContent = evt.target.value;
        $id('manual-feed-slider').value = 0;
        $id('manual-feed-info').textContent = '0';
    });

    $id('manual-feed-slider').addEventListener('input', function (evt) {
        $id('manual-feed-info').textContent = evt.target.value;
        $id('manual-charge-slider').value = 0;
        $id('manual-charge-info').textContent = '0';
    });

    $id('btn-manual-wakeup').addEventListener('click', function () {
        app.manual_cmd = 'wakeup';
    });
    $id('btn-manual-sleep').addEventListener('click', function () {
        app.manual_cmd = 'sleep';
    });

    app.poll_state();
}

/**
 * Cyclic polling the status (/api/status)
 */
app.poll_state = function () {
    let self = app;
    let post = null;

    // nur mit lokal aktiviertem manual wird gesendet

    if (self.state?.manual_auth) {
        post = {'manual_set_p': $id('manual-charge-slider').value - $id('manual-feed-slider').value};
        if (self.manual_cmd) post['manual_cmd'] = self.manual_cmd;
        self.manual_cmd = null;
        console.log('manual', post)
    }

    fetch_json('api/state',
        function (response) {
            self.show_state(response)
        }, function (error) {
            console.log('poll_state ERROR', error);
            self.show_state(null)
        }, post);
    setTimeout(self.poll_state, 1000);
};

/**
 * Successfull poll
 *
 * @param state
 */
app.show_state = function (state) {
    let self = app;

    // state.ess.state = 'error';  // Fake for test
    // state.meterhub.error = 'error';  // Fake for test
    // state.multiplus.error = 'error';  // Fake for test
    // state.bms.error = 'error';  // Fake for test
    // console.log(state);

    // fake state
    // state.ess.time = "2022-11-21 14:54";
    // state.ess.info = "Automatik - Laden";
    // state.meterhub.pv1_p = 1265;
    // state.meterhub.pv2_p = 1608;
    // state.meterhub.pv_p = 2873;
    // state.meterhub.home_p = 432;
    // state.meterhub.bat_p = 1602;
    // state.meterhub.grid_p = -839;
    // state.bms.soc = 81;

    self.state = state;

    // reload if session is invalid

    if (state?.session_invalid === true) {
        console.log("received state.session_invalid");
        document.body.innerHTML = "<h2 style='text-align: center'>Invalid session</h2><h2 style='text-align: center'>starting reload...</h2>";
        setTimeout(function () {
            location.reload();
        }, 2000);
    }

    // add frame in manual mode

    let ele = $id('container-main');
    if (state?.ess?.mode === 'manual') {
        if (state?.manual_auth === true) ele.style.border = '10px solid #ec3030';
        else ele.style.border = '10px solid #fda042';
    } else {
        ele.style.border = null;
    }

    // show time in headline
    try {
        $id('time').textContent = state.ess.time.slice(11)
    } catch (e) {
        $id('time').textContent = "DISCONNECTED";
    }

    self.show_dashboard_state(state)
    self.show_detail_values(state);
}

/**
 * Show state for main dashboard view
 *
 * @param state
 */
app.show_dashboard_state = function (state) {
    let self = app;

    // === PFlow ===
    let d = {
        pv: {
            power: state?.meterhub?.pv_p,
            subline: 'Süd: ' + (state?.meterhub?.pv1_p ?? '---') + ' W  Nord: ' + (state?.meterhub?.pv2_p ?? '---') + ' W',
        },
        home: {power: state?.meterhub?.home_p},
        bat: {
            power: state?.meterhub?.bat_p,
            error: state?.ess?.state === 'error',
            info: (state?.bms?.soc) ? state.bms.soc + ' %' : '-- %',
            subline: state?.ess?.info
        },
        car: {
            power: state?.meterhub?.car_p,
            disable: !state?.meterhub?.car_plug,
            info: ((state?.meterhub?.car_e_cycle ?? 0) > 0) ? (state?.meterhub?.car_e_cycle / 1000).toFixed(1) + ' kWh' : '',
            subline: state?.meterhub?.car_info,

            wallbox_pvready: state?.meterhub?.car_pv_ready,
            wallbox_stop: state?.meterhub?.car_stop,
            wallbox_amp: (state?.meterhub?.car_phase && state?.meterhub?.car_amp) ? state?.meterhub?.car_phase + 'x' + state?.meterhub?.car_amp + 'A' : 'xxx'

        },
        heat: {
            power: state?.meterhub?.heat_p
        },
        grid: {
            power: state?.meterhub?.grid_p
        }
    };
    self.pflow.update(d);
    $id('option-select').value = state?.ess?.setting ?? '';
}

/**
 * Show state for detail view
 *
 * @param state
 */
app.show_detail_values = function (state) {
    let self = app;

    set_val = function (id, value, suffix, precision) {
        $id(id).textContent = fmtNumber(value, precision) + suffix;
    }

    // set mode buttons
    document.querySelectorAll("[data-mode]").forEach(button => {
        let b = (button.getAttribute('data-mode') === state?.ess?.mode);
        button.classList.toggle('btn-primary', b);
        button.classList.toggle('btn-outline-primary', !b);
    });

    // set title on error
    $id('meterhub-title').style.backgroundColor = (state?.meterhub?.error) ? '#ff4f4f' : '#fff';
    $id('mp2-title').style.backgroundColor = (state?.multiplus?.error) ? '#ff4f4f' : '#fff';
    $id('bms-title').style.backgroundColor = (state?.bms?.error) ? '#ff4f4f' : '#fff';

    // show reset button on error
    $id('btn-error-reset').style.display = (state?.ess?.state === 'error') ? 'block' : 'none';

    // ess table values
    set_val('ess-set-p', state?.ess?.set_p, ' W');
    $id('ess-mode').textContent = state?.ess?.mode ?? '?';
    $id('ess-state').textContent = state?.ess?.state ?? '?';

    // Meterhub
    // let car_p = state?.meterhub?.car_p;
    // let home_all_p = state?.meterhub?.home_all_p;
    // let home_p = home_all_p === null || car_p === null ? home_all_p : home_all_p - car_p;

    set_val('meter-pv-p', state?.meterhub?.pv_p, ' W');
    set_val('meter-grid-p', state?.meterhub?.grid_p, ' W');
    set_val('meter-home-p', state?.meterhub?.home_p, ' W');
    set_val('meter-bat-p', state?.meterhub?.bat_p, ' W');
    if(config_enable_car) set_val('meter-car-p', state?.meterhub?.car_p, ' W');
    if(config_enable_heat) set_val('meter-heat-p', state?.meterhub?.heat_p, ' W');

    // Multiplus
    $id('mp2-state').textContent = state?.multiplus?.state ?? '--';
    set_val('mp2-inv-p', state?.multiplus?.inv_p, ' W');
    set_val('mp2-bat-p', state?.multiplus?.bat_p, ' W');
    set_val('mp2-bat-u', state?.multiplus?.bat_u, ' V', 1);
    set_val('mp2-bat-i', state?.multiplus?.bat_i, ' A', 1);
    set_val('mp2-mains-u', state?.multiplus?.mains_u, ' V', 1);
    set_val('mp2-mains-i', state?.multiplus?.mains_i, ' A', 1);

    // BMS / US2000
    for (let n = 0; n < (state?.bms?.u_pack ?? []).length; n++) {
        let u = state?.bms?.u_pack?.[n];
        let i = state?.bms?.i_pack?.[n];
        let p = u === null || i === null ? null : u * i;

        try {
            set_val('bms-soc' + n, state?.bms?.soc_pack?.[n], '%');
            set_val('bms-p' + n, p, 'W');
            set_val('bms-u' + n, u, 'V', 2);
            set_val('bms-i' + n, i, 'A', 1);
            set_val('bms-t' + n, state?.bms?.t_pack?.[n], '°C');
            set_val('bms-cycle' + n, state?.bms?.cycle_pack?.[n], 'x');
        } catch (e) {
        }
    }
    $id('container-manual').style.display = (state?.manual_auth === true) ? 'block' : 'none';
}


window.onload = function () {
    app.init();
}

