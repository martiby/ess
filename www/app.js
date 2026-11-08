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
    $id('btn-manual-shutdown').addEventListener('click', function () {
        if (confirm('Raspberry wirklich herunterfahren? Das ESS ist danach aus, Neustart nur durch Strom aus/ein.')) app.manual_cmd = 'shutdown';
    });
    $id('btn-manual-reboot').addEventListener('click', function () {
        if (confirm('Raspberry wirklich neu starten?')) app.manual_cmd = 'reboot';
    });

    // BMS pack: toggle cell voltage table
    document.querySelectorAll('.bms-toggle').forEach(function (ele) {
        ele.addEventListener('click', function () {
            let n = ele.getAttribute('data-pack');
            let row = $id('bms-cells' + n);
            let open = row.style.display === 'none';
            row.style.display = open ? 'table-row' : 'none';
            $id('bms-arrow' + n).innerHTML = open ? '&#9662;' : '&#9656;';
            if (open) app.poll_cells();
        });
    });

    // Raspberry health view
    let health_show = function (open) {
        $id('container-health').style.display = open ? 'flex' : 'none';
        if (open) app.poll_health();
    };
    $id('health-logo').addEventListener('click', function () {
        health_show($id('container-health').style.display === 'none');
    });
    $id('health-close').addEventListener('click', function () {
        health_show(false);
    });
    $id('container-health').addEventListener('click', function (evt) {
        if (evt.target === this) health_show(false);  // click outside the box
    });
    document.addEventListener('keydown', function (evt) {
        if (evt.key === 'Escape') health_show(false);
    });

    app.poll_state();
}

/**
 * Raspberry health data (/api/health), polled every 2s while the view is open
 */
app.poll_health = function () {
    if ($id('container-health').style.display === 'none') return;
    fetch_json('api/health', function (h) {
        app.show_health(h);
    }, function (error) {
        console.log('poll_health ERROR', error);
    });
    clearTimeout(app.health_timer);  // only one polling loop, also after fast close / open
    app.health_timer = setTimeout(app.poll_health, 2000);
};

app.show_health = function (h) {
    let txt = function (id, value) {
        $id(id).textContent = value;
    };
    let v = function (value, suffix) {
        return (value === null || value === undefined) ? '--' : value + (suffix ?? '');
    };
    let warn = function (id, on) {
        $id(id).style.color = on ? '#d93025' : '';
        $id(id).style.fontWeight = on ? 'bold' : '';
    };

    txt('health-host', v(h?.hostname, ''));
    txt('health-model', v(h?.model) + ', Kernel ' + v(h?.kernel));
    txt('health-uptime', v(h?.uptime));
    txt('health-cpu', v(h?.cpu_percent, ' %') + '  (Systemlast ' + (h?.cpu_load ?? []).join(' / ') + ', ' + v(h?.cpu_count) + ' Kerne)');
    warn('health-cpu', (h?.cpu_percent ?? 0) >= 80);
    txt('health-temp', v(h?.cpu_temp, ' °C') + ' / ' + v(h?.cpu_mhz, ' MHz'));
    warn('health-temp', (h?.cpu_temp ?? 0) >= 70);
    let thr = h?.throttled_info ?? [];
    txt('health-throttled', h?.throttled === null ? '--' : (thr.length ? thr.join(', ') : 'OK'));
    warn('health-throttled', thr.length > 0);
    txt('health-ram', v(h?.ram_used_mb) + ' / ' + v(h?.ram_total_mb, ' MB') + '  (' + v(h?.ram_percent, ' %') + ')'
        + ((h?.swap_used_mb ?? 0) > 0 ? ', Swap ' + h.swap_used_mb + ' MB' : ''));
    warn('health-ram', (h?.ram_percent ?? 0) >= 85);

    let rows = '';
    (h?.net ?? []).forEach(function (n) {
        let name = n.name === 'eth0' ? 'LAN (eth0)' : (n.name === 'wlan0' ? 'WLAN (wlan0)' : n.name);
        let info = '&darr; ' + v(n.rx_kbit, ' kbit/s') + ' &nbsp;&uarr; ' + v(n.tx_kbit, ' kbit/s');
        let extra = [{up: 'verbunden', down: 'getrennt', unknown: 'aktiv'}[n.state] ?? n.state];
        if (n.speed_mbit) extra.push(n.speed_mbit + ' Mbit');
        if (n.signal_dbm !== undefined && n.signal_dbm !== null) extra.push('Signal ' + n.signal_dbm + ' dBm');
        extra.push('gesamt &darr;' + n.rx_total_mb + ' / &uarr;' + n.tx_total_mb + ' MB');
        rows += '<tr class="health-net-row"><td>' + name + '</td><td class="text-right">' + info
            + '<br><span style="font-size: 11px; color: #888888">' + extra.join(', ') + '</span></td></tr>';
    });
    document.querySelectorAll('.health-net-row').forEach(r => r.remove());  // same tbody -> row colors continue
    $id('health-ram-row').insertAdjacentHTML('afterend', rows);

    let disk = function (id, d) {
        txt(id, d ? d.used_gb + ' / ' + d.total_gb + ' GB  (' + d.percent + ' %)' : '--');
        warn(id, (d?.percent ?? 0) >= 85);
    };
    disk('health-disk-root', h?.disk_root);
    disk('health-disk-boot', h?.disk_boot);

    let sd = h?.sd ?? {};
    txt('health-sd', v(sd.manufacturer) + ' ' + v(sd.name) + ', ' + v(sd.size_gb, ' GB') + ', Herstellung ' + v(sd.date)
        + (sd.readonly ? ', NUR LESEN!' : '') + (sd.life_time ? ', Lebensdauer ' + sd.life_time : ''));
    warn('health-sd', sd.readonly === true);
    txt('health-sd-write', v(sd.written_mb, ' MB') + '  (Ø ' + v(sd.write_mb_day, ' MB/Tag') + ', aktuell ' + v(sd.write_kb_s, ' kB/s') + ')');
    txt('health-sd-errors', v(sd.errors));
    warn('health-sd-errors', (sd.errors ?? 0) > 0);
};

/**
 * Read cell voltages (/api/bms), only if a cell table is open
 */
app.poll_cells = function () {
    let open = Array.from(document.querySelectorAll('[id^="bms-cells"]')).some(r => r.style.display !== 'none');
    if (!open) return;
    fetch_json('api/bms', function (bms) {
        (bms?.analog ?? []).forEach(function (pack, n) {
            let u = pack?.u_cell ?? [];
            let valid = u.filter(v => typeof v === 'number');
            let u_min = valid.length ? Math.min(...valid) : null;
            let u_max = valid.length ? Math.max(...valid) : null;
            for (let c = 0; c < 15; c++) {
                let ele = $id('cell' + n + '-' + c);
                if (!ele) continue;
                let v = u[c];
                ele.textContent = (typeof v === 'number') ? v : '--';
                ele.classList.toggle('cell-min', valid.length > 1 && u_min !== u_max && v === u_min);
                ele.classList.toggle('cell-max', valid.length > 1 && u_min !== u_max && v === u_max);
            }
            let info = bms?.info?.[n] ?? {};
            let id_text = [];
            if (info.serial) id_text.push('S/N ' + info.serial);
            if (info.firmware) id_text.push('Firmware ' + info.firmware + ' (' + info.firmware_main + ')');
            $id('bms-id' + n).textContent = id_text.length ? id_text.join(' \u00b7 ') : '--';
            let lim = info.limit;
            let num = (v, dec) => v.toFixed(dec).replace('.', ',');
            $id('bms-limit' + n).textContent = lim
                ? 'Laden: ' + (lim.chg_on ? 'erlaubt' : 'gesperrt') + ', max. ' + num(lim.i_chg, 0) + ' A bis ' + num(lim.u_chg, 1) + ' V'
                  + ' \u00b7 Entladen: ' + (lim.dis_on ? 'erlaubt' : 'gesperrt') + ', max. ' + num(lim.i_dis, 0) + ' A bis ' + num(lim.u_dis, 1) + ' V'
                : '--';
            let d = $id('cell' + n + '-delta');
            if (d) {
                d.textContent = (u_min === null) ? '--' : (u_max - u_min);
                d.classList.toggle('cell-delta-high', u_min !== null && (u_max - u_min) >= 30);
            }
        });
    });
};

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
    self.poll_cells();
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
        document.body.innerHTML = "<h2 style='text-align: center'>Sitzung ungültig</h2><h2 style='text-align: center'>Seite wird neu geladen ...</h2>";
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
        $id('time').textContent = "KEINE VERBINDUNG";
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
            power: state?.meterhub?.pv_p   //,
            //subline: 'Süd: ' + (state?.meterhub?.pv1_p ?? '---') + ' W  Nord: ' + (state?.meterhub?.pv2_p ?? '---') + ' W',
        },
        home: {power: state?.meterhub?.home_p},
        bat: {
            power: state?.multiplus?.bat_p,
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
    //set_val('meter-bat-p', state?.meterhub?.bat_p, ' W');
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
    for (let n = 0; n < (state?.bms?.pack_u ?? []).length; n++) {
        let u = state?.bms?.pack_u?.[n];
        let i = state?.bms?.pack_i?.[n];
        let p = u === null || i === null ? null : u * i;

        try {
            set_val('bms-soc' + n, state?.bms?.pack_soc?.[n], '%');
            set_val('bms-p' + n, p, 'W');
            set_val('bms-u' + n, u, 'V', 2);
            set_val('bms-i' + n, i, 'A', 1);
            set_val('bms-t' + n, state?.bms?.pack_t?.[n], '°C');
            set_val('bms-cycle' + n, state?.bms?.pack_cycle?.[n], 'x');
        } catch (e) {
        }
    }
    $id('container-manual').style.display = (state?.manual_auth === true) ? 'block' : 'none';
}


window.onload = function () {
    app.init();
}

