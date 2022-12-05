/**

 HTML/Javascript view for energy flow in building automation

 Setup example:
 var config = {
    table: [
        {id: 'pv', type: 'pv'},
        {id: 'home', type: 'home', sign: -1},
        {id: 'bat', type: 'bat', sign: -1},
        {id: 'grid', type: 'grid'},
        {id: 'car', type: 'car', sign: -1, wallbox: true}],
    bar: {
        in: [
            {id: 'pv', type: 'pv'},
            {id: 'bat', type: 'bat', sign: -1},
            {id: 'grid', type: 'grid'}],
        out: [
            {id: 'home', type: 'home'},
            {id: 'car', type: 'car'},
            {id: 'bat', type: 'bat'},
            {id: 'grid', type: 'grid', sign: -1}]
    }
 }
 pflow = new Pflow('pflow-table', 'pflow-bar', setup);


 Data example:
 var d = {
    pv: {
        power: 2533,
        subline: 'Süd: 600 W  Nord: 400 W'},
    home: {
        power: 411 },
    bat: {
        power: 0,
        info: '90%',
        subline: 'Automatik - Schlafen'},
    car: {
        power: 0,
        info: '11.2 kWh',
        subline: 'PV - Laden gesperrt',
        disable: false,
        wallbox_pvready: false,
        wallbox_stop: true,
        wallbox_amp: '1x6A'},
    grid: {
        power: -2122
    },
 };

 pflow.update(d);

 Config details:

 table
 id       identifier for access
 type     set to use default color and icon [pv, home, bat, grid, car heat]
 sign     -1 to invert the direction for the arrow
 icon     manual icon setting, e.g.: 'svg-house'
 wallbox  true to activate wallbox options

 bar.*
 id       identifier for access
 type     set to use default color and icon [pv, home, bat, grid, car heat]
 sign     -1 for negative power input to be positive
 icon     manual icon setting, e.g.: 'svg-house'

 Data details:

 power:   Power in watt
 info:    Text behind power
 subline: Infotext below power and info
 disable: Icon is shown disabled
 error:   Icon is shown as error

 wallbox_pvready: sun or cloud icon
 wallbox_stop:    badge with phase and ampere is shown diabled
 wallbox_amp:     Badge for phase and ampere info '3x16A'


 07.11.2022 Martin Steppuhn
 26.11.2022 Martin Steppuhn     error for icon


 */

class Pflow {
    /**
     * Constructor/Init
     *
     * @param table_id  Element ID for the table view
     * @param bar_id Element ID for the bars view
     * @param config Configuration
     */
    constructor(table_id, bar_id, config) {
        this.table_id = table_id;  // container for table
        this.bar_id = bar_id; // container for in and out bar
        this.config = config;  // complete configuration
        this.arrow_power_scale = 2000;  // power in watt for max arrow size

        // if not specified in config, the icon ist dedicated by the type  pv --> svg-sun
        this.default_icons = {
            pv: 'svg-sun',
            home: 'svg-house',
            bat: 'svg-car-battery',
            grid: 'svg-industry',
            car: 'svg-car',
            heat: 'svg-fire'
        };

        // Init
        this.init_resource();   // append svgs and styles
        this.init_table();
        this.init_bar('in');
        this.init_bar('out');
        this.update();
    }

    /**
     * Init table view
     */
    init_table() {
        var element = document.getElementById(this.table_id);

        if (!element || !(this.config?.table ?? null)) {   // abort without container or config
            this.config.table = null;
            return;
        }

        var s = '';
        var cfg = this.config.table;
        for (var i = 0; i < cfg.length; i++) {
            var row = cfg[i];

            if (row.wallbox) {
                var wallbox = `<svg data-id="wallbox-sun" viewBox="0 0 100 100" ><use href="#svg-sun"/></svg>
                               <svg data-id="wallbox-cloud" viewBox="0 0 100 100"><use href="#svg-cloud"/></svg>
                               <div data-id="wallbox-amp"></div>`;
            } else wallbox = "";

            var svg_icon = row?.icon ?? this.default_icons[row.type];  // get custom or default icon

            // "Template" for a single table row
            s += `
            <div data-row="${row.id}" data-type="${row.type}" class="pft-row" style="position: relative; width: 100%;">
                <div class="pft-col-a" style="position: absolute; height: 100%">
                        <svg class="pft-icon-container pft-absolute-center" viewBox="-50 -50 100 100">
                            <path data-id="arrow" stroke-linecap="round" stroke-linejoin="round" fill="none"></path>
                        </svg>
                </div>    
                <div class="pft-col-b" style="position: absolute; height: 100%">
                    <div class="pft-icon-container pft-absolute-center">
                        <svg data-id="icon" class="pft-absolute-center" width="100%" viewBox="0 0 100 100"><use href="#${svg_icon}"/></svg>
                        ${wallbox}
                    </div>
                </div>


                <div class="pft-col-c" style="position: absolute; height: 100%">
                    <div style="position: relative; height: 100%;">
                        <div style="position: absolute; top: 50%; transform: translate(0%, -50%);"> 
                            <span data-id="power"></span>
                            <span data-id="info"></span>
                            <div data-id="subline"></div>
                        </div>    
                   </div>     
                                            
                </div>
            </div>`;
        }
        element.innerHTML = s;
    }

    /**
     * Init bar
     */
    init_bar(bar_name) {
        var element = document.getElementById(this.bar_id)
        var cfg = this.config?.bar?.[bar_name] ?? null;

        if (element && cfg) {
            var s = `<div data-bar=${bar_name}  class="pfb-progress">`;
            for (var i = 0; i < cfg.length; i++) {
                var bar = cfg[i];
                var svg_icon = bar?.icon ?? this.default_icons[bar.type];
                s += `<div data-id="${bar.id}" data-type="${bar.type}" class="pfb-progress-bar">
                        <svg viewBox="0 0 100 100"><use href="#${svg_icon}"/></svg>
                    </div>`;
            }
            element.innerHTML += s;
        } else {
            this.config.bar = null;   // disable by removing the config
        }

    }

    /**
     * Update table and bars
     */
    update(data) {
        this.update_table(data);
        this.update_bar('in', data);
        this.update_bar('out', data);
    }

    /**
     * Update table with given data
     *
     *  For each entry the following values could be set: [disable, power, info, subline]
     *  and anditional with wallbox option: [wallbox_pvready, wallbox_stop, wallbox_amp]
     *
     * @param data
     */
    update_table(data) {
        if (!this.config.table) return;

        data = data || {};

        for (var row of this.config.table) {
            var d = data?.[row.id] ?? {};
            var id = row.id;
            var row_element = document.querySelector(`#${this.table_id} [data-row="${id}"]`);
            var p = (data?.[id]?.power ?? 0) * (row?.sign ?? 1);

            this.update_table_arrow(row_element.querySelector('[data-id="arrow"]'), p);

            // === Icon ===
            row_element.querySelector('[data-id="icon"]').classList.toggle('pft-fill-error', (d?.error ?? false));
            row_element.querySelector('[data-id="icon"]').classList.toggle('pft-fill-disable', (d?.disable ?? false));
            row_element.querySelector('[data-id="icon"]').classList.toggle('pft-fill-enable', !(d?.disable ?? false) && !(d?.error ?? false));

            // === Text ===
            row_element.querySelector('[data-id="power"]').textContent = (isNaN(d.power)) ? '--- W' : Math.abs(d.power) + ' W';
            row_element.querySelector('[data-id="info"]').textContent = d?.info ?? '';
            row_element.querySelector('[data-id="subline"]').textContent = d?.subline ?? '';

            // === Wallbox ===
            if (d?.wallbox_pvready === true) {
                row_element.querySelector('[data-id="wallbox-sun"]').setAttribute('visibility', 'visible');
                row_element.querySelector('[data-id="wallbox-cloud"]').setAttribute('visibility', 'hidden');
            } else if (d?.wallbox_pvready === false) {
                row_element.querySelector('[data-id="wallbox-sun"]').setAttribute('visibility', 'hidden');
                row_element.querySelector('[data-id="wallbox-cloud"]').setAttribute('visibility', 'visible');
            }

            var ele = row_element.querySelector('[data-id="wallbox-amp"]');
            if (ele) {
                ele.classList.toggle('pft-wallbox-off', (d?.wallbox_stop === true));
                ele.classList.toggle('pft-wallbox-on', (d?.wallbox_stop === false));
                ele.textContent = d?.wallbox_amp ?? '';
            }
        }
    }

    /**
     * Update single arrow for a table row.
     *
     * @param element  HTML Element
     * @param value Power value in watt
     */
    update_table_arrow(element, value) {
        value = (value / this.arrow_power_scale) * 100;  // power for 100%

        var sign = (value > 0) ? -1 : 1;
        if (value > 100) value = 100;
        if (value < -100) value = -100;
        var line_width = this.scale_value(Math.abs(value), 5, 20);

        // console.log("arrow_update", sid, value, invert);

        if (value) {
            var d = this.scale_value(Math.abs(value), 10, 50 - line_width) * sign;
            element.setAttribute('d', `M ${-d / 2} ${-d} L ${d / 2} 0 L ${-d / 2} ${+d}`);
            element.setAttribute('stroke-width', line_width);
        } else {
            element.setAttribute('d', '');
        }
    }

    /**
     * Scale a 0..100% variable between two borders
     *
     * @param value
     * @param min
     * @param max
     * @returns value [min..max]
     */
    scale_value(value, min, max) {
        value = ((max - min) / 100) * value + min;
        if (value > max) value = max;
        return value;
    }

    /**
     * Update bar
     *
     * @param bar_name in/out
     * @data data
     */
    update_bar(bar_name, data) {
        var n, i, p;
        var bar;
        var cfg = this.config?.bar?.[bar_name] ?? null;

        if (!cfg) return;

        var sum = 0;

        for (i = 0; i < cfg.length; i++) {
            bar = cfg[i];
            p = parseInt(data?.[bar.id]?.power ?? 0) * (bar?.sign ?? 1);
            sum += Math.max(0, p);
        }

        var percentage;
        var percentage_sum = 0;

        var element = document.querySelector(`#${this.bar_id} [data-bar=${bar_name}]`);

        // console.log("!!!", element);

        for (i = 0; i < cfg.length; i++) {
            bar = cfg[i];
            p = parseInt(data?.[bar.id]?.power ?? 0) * (bar?.sign ?? 1);
            p = Math.max(0, p);

            if (i < cfg.length - 1) {
                percentage = Math.round((p / sum) * 100);
                percentage_sum += percentage;
            } else
                percentage = 100 - percentage_sum;

            // console.log("update_bar", n, i, sum, bar, p, percentage);
            element.querySelector('[data-id="' + bar.id + '"]').style.width = percentage + '%';
        }
    }

    /**
     * Init resources
     */
    init_resource() {
        if (document.getElementById('pflow-resource')) return;   // resource already defined
        var resource = `
        <svg id="pflow-resource" style="display: none">
            <g>
            <svg id="svg-sun" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
                <!--! Font Awesome Free 6.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free (Icons: CC BY 4.0, Fonts: SIL OFL 1.1, Code: MIT License) Copyright 2022 Fonticons, Inc. -->
                <path d="M361.5 1.2c5 2.1 8.6 6.6 9.6 11.9L391 121l107.9 19.8c5.3 1 9.8 4.6 11.9 9.6s1.5 10.7-1.6 15.2L446.9 256l62.3 90.3c3.1 4.5 3.7 10.2 1.6 15.2s-6.6 8.6-11.9 9.6L391 391 371.1 498.9c-1 5.3-4.6 9.8-9.6 11.9s-10.7 1.5-15.2-1.6L256 446.9l-90.3 62.3c-4.5 3.1-10.2 3.7-15.2 1.6s-8.6-6.6-9.6-11.9L121 391 13.1 371.1c-5.3-1-9.8-4.6-11.9-9.6s-1.5-10.7 1.6-15.2L65.1 256 2.8 165.7c-3.1-4.5-3.7-10.2-1.6-15.2s6.6-8.6 11.9-9.6L121 121 140.9 13.1c1-5.3 4.6-9.8 9.6-11.9s10.7-1.5 15.2 1.6L256 65.1 346.3 2.8c4.5-3.1 10.2-3.7 15.2-1.6zM352 256c0 53-43 96-96 96s-96-43-96-96s43-96 96-96s96 43 96 96zm32 0c0-70.7-57.3-128-128-128s-128 57.3-128 128s57.3 128 128 128s128-57.3 128-128z"/>
            </svg>
            <svg x="10" y="25" width="10" height="10" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 576 512">
                <!--! Font Awesome Free 6.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free (Icons: CC BY 4.0, Fonts: SIL OFL 1.1, Code: MIT License) Copyright 2022 Fonticons, Inc. -->
                <path d="M575.8 255.5c0 18-15 32.1-32 32.1h-32l.7 160.2c0 2.7-.2 5.4-.5 8.1V472c0 22.1-17.9 40-40 40H456c-1.1 0-2.2 0-3.3-.1c-1.4 .1-2.8 .1-4.2 .1H416 392c-22.1 0-40-17.9-40-40V448 384c0-17.7-14.3-32-32-32H256c-17.7 0-32 14.3-32 32v64 24c0 22.1-17.9 40-40 40H160 128.1c-1.5 0-3-.1-4.5-.2c-1.2 .1-2.4 .2-3.6 .2H104c-22.1 0-40-17.9-40-40V360c0-.9 0-1.9 .1-2.8V287.6H32c-18 0-32-14-32-32.1c0-9 3-17 10-24L266.4 8c7-7 15-8 22-8s15 2 21 7L564.8 231.5c8 7 12 15 11 24z"/>
            </svg>
            <svg id="svg-house" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 576 512">
                <!--! Font Awesome Free 6.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free (Icons: CC BY 4.0, Fonts: SIL OFL 1.1, Code: MIT License) Copyright 2022 Fonticons, Inc. -->
                <path d="M575.8 255.5c0 18-15 32.1-32 32.1h-32l.7 160.2c0 2.7-.2 5.4-.5 8.1V472c0 22.1-17.9 40-40 40H456c-1.1 0-2.2 0-3.3-.1c-1.4 .1-2.8 .1-4.2 .1H416 392c-22.1 0-40-17.9-40-40V448 384c0-17.7-14.3-32-32-32H256c-17.7 0-32 14.3-32 32v64 24c0 22.1-17.9 40-40 40H160 128.1c-1.5 0-3-.1-4.5-.2c-1.2 .1-2.4 .2-3.6 .2H104c-22.1 0-40-17.9-40-40V360c0-.9 0-1.9 .1-2.8V287.6H32c-18 0-32-14-32-32.1c0-9 3-17 10-24L266.4 8c7-7 15-8 22-8s15 2 21 7L564.8 231.5c8 7 12 15 11 24z"/>
            </svg>
            <svg id="svg-car-battery" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
                <!--! Font Awesome Free 6.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free (Icons: CC BY 4.0, Fonts: SIL OFL 1.1, Code: MIT License) Copyright 2022 Fonticons, Inc. -->
                <path d="M80 96c0-17.7 14.3-32 32-32h64c17.7 0 32 14.3 32 32l96 0c0-17.7 14.3-32 32-32h64c17.7 0 32 14.3 32 32h16c35.3 0 64 28.7 64 64V384c0 35.3-28.7 64-64 64H64c-35.3 0-64-28.7-64-64V160c0-35.3 28.7-64 64-64l16 0zm304 96c0-8.8-7.2-16-16-16s-16 7.2-16 16v32H320c-8.8 0-16 7.2-16 16s7.2 16 16 16h32v32c0 8.8 7.2 16 16 16s16-7.2 16-16V256h32c8.8 0 16-7.2 16-16s-7.2-16-16-16H384V192zM80 240c0 8.8 7.2 16 16 16h96c8.8 0 16-7.2 16-16s-7.2-16-16-16H96c-8.8 0-16 7.2-16 16z"/>
            </svg>
            <svg id="svg-industry" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
                <!--! Font Awesome Free 6.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free (Icons: CC BY 4.0, Fonts: SIL OFL 1.1, Code: MIT License) Copyright 2022 Fonticons, Inc. -->
                <path d="M32 32C14.3 32 0 46.3 0 64V304v48 80c0 26.5 21.5 48 48 48H464c26.5 0 48-21.5 48-48V304 152.2c0-18.2-19.4-29.7-35.4-21.1L320 215.4V152.2c0-18.2-19.4-29.7-35.4-21.1L128 215.4V64c0-17.7-14.3-32-32-32H32z"/>
            </svg>
            <svg id="svg-car" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
                <!--! Font Awesome Free 6.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free (Icons: CC BY 4.0, Fonts: SIL OFL 1.1, Code: MIT License) Copyright 2022 Fonticons, Inc. -->
                <path d="M135.2 117.4L109.1 192H402.9l-26.1-74.6C372.3 104.6 360.2 96 346.6 96H165.4c-13.6 0-25.7 8.6-30.2 21.4zM39.6 196.8L74.8 96.3C88.3 57.8 124.6 32 165.4 32H346.6c40.8 0 77.1 25.8 90.6 64.3l35.2 100.5c23.2 9.6 39.6 32.5 39.6 59.2V400v48c0 17.7-14.3 32-32 32H448c-17.7 0-32-14.3-32-32V400H96v48c0 17.7-14.3 32-32 32H32c-17.7 0-32-14.3-32-32V400 256c0-26.7 16.4-49.6 39.6-59.2zM128 288c0-17.7-14.3-32-32-32s-32 14.3-32 32s14.3 32 32 32s32-14.3 32-32zm288 32c17.7 0 32-14.3 32-32s-14.3-32-32-32s-32 14.3-32 32s14.3 32 32 32z"/>
            </svg>
            <svg id="svg-cloud" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 512"><!--! Font Awesome Free 6.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free (Icons: CC BY 4.0, Fonts: SIL OFL 1.1, Code: MIT License) Copyright 2022 Fonticons, Inc. --><path d="M0 336c0 79.5 64.5 144 144 144H512c70.7 0 128-57.3 128-128c0-61.9-44-113.6-102.4-125.4c4.1-10.7 6.4-22.4 6.4-34.6c0-53-43-96-96-96c-19.7 0-38.1 6-53.3 16.2C367 64.2 315.3 32 256 32C167.6 32 96 103.6 96 192c0 2.7 .1 5.4 .2 8.1C40.2 219.8 0 273.2 0 336z"/></svg>
            <svg id="svg-fire" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--! Font Awesome Free 6.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free (Icons: CC BY 4.0, Fonts: SIL OFL 1.1, Code: MIT License) Copyright 2022 Fonticons, Inc. --><path d="M159.3 5.4c7.8-7.3 19.9-7.2 27.7 .1c27.6 25.9 53.5 53.8 77.7 84c11-14.4 23.5-30.1 37-42.9c7.9-7.4 20.1-7.4 28 .1c34.6 33 63.9 76.6 84.5 118c20.3 40.8 33.8 82.5 33.8 111.9C448 404.2 348.2 512 224 512C98.4 512 0 404.1 0 276.5c0-38.4 17.8-85.3 45.4-131.7C73.3 97.7 112.7 48.6 159.3 5.4zM225.7 416c25.3 0 47.7-7 68.8-21c42.1-29.4 53.4-88.2 28.1-134.4c-2.8-5.6-5.6-11.2-9.8-16.8l-50.6 58.8s-81.4-103.6-87.1-110.6C133.1 243.8 112 273.2 112 306.8C112 375.4 162.6 416 225.7 416z"/></svg>
            </g>
        </svg>
        <style>
            :root {
                --color-pv:   #FFD54F;
                --color-home: #0d6efd;
                --color-heat: #d36c6c;
                --color-bat:  #81C784;
                --color-grid: #917a71;
                --color-car:  #9FA8DA;
                
                --color-base: #606060;
                --color-active: #0d6efd;
                --color-disable: #c8c8c8;
                --color-error: #ff0000;
                --color-secondary: #909090;
                --font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", "Noto Sans", "Liberation Sans", Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji";
            }
    
            /* === Table === */
            .pft-row            { height: 62px; }
            .pft-icon-container { height: 35px; width:35px; }
            .pft-fill-disable   { fill: var(--color-disable); }    
            .pft-fill-error     { fill: var(--color-error); }
            .pft-fill-enable    { fill: var(--color-base); }
            /*.pflow-text-container { margin-left: 20px; }*/
            
            .pft-col-a { left:  0%; width: 12%; }
            .pft-col-b { left: 12%; width: 15%; }
            .pft-col-c { left: 35%; width: 65%; }
            
            @media (min-width: 768px) {
                .pft-col-a { left: 0%; width: 10%; }
                .pft-col-b { left: 10%; width: 8%; }
                .pft-col-c { left: 23%; width: 77%; }
            }            
            
            .pft-row [data-id=power]   { font-size: 28px; font-family: var(--font-family); color: var(--color-base); }
            .pft-row [data-id=info]    { font-size: 16px; font-family: var(--font-family); color: var(--color-base); margin-left: 5px; }
            .pft-row [data-id=subline] { font-size: 16px; font-family: var(--font-family); color: var(--color-base); }
                
            .pft-row[data-type=pv]   { stroke: var(--color-pv); }
            .pft-row[data-type=home] { stroke: var(--color-home); }
            .pft-row[data-type=bat]  { stroke: var(--color-bat); }
            .pft-row[data-type=grid] { stroke: var(--color-grid); }
            .pft-row[data-type=car]  { stroke: var(--color-car); }
            .pft-row[data-type=heat] { stroke: var(--color-heat); }
            
            /* === Wallbox === */
        
            .pft-wallbox-on  { background-color: var(--color-active); }
            .pft-wallbox-off { background-color: var(--color-secondary); }
        
            .pft-row [data-id=wallbox-sun] {
                height: 21px;
                position: absolute; top: 0; right: 0;
                transform: translate(50%, -50%);
                fill: var(--color-pv);
            }        
        
            .pft-row [data-id=wallbox-cloud] {
                height: 21px;
                position: absolute; top: 0; right: 0; 
                transform: translate(50%, -50%);
                fill: var(--color-secondary);
            }        
        
            .pft-row [data-id=wallbox-amp] {
                font-size: 10px;
                font-weight: 700;
                line-height: 1;
                color: #fff;
                text-align: center;
                padding: 4px 6px;
                position: absolute; bottom: 0; right: 0;
                border-radius: 12px;
                transform: translate(50%, +50%);
            }
            
            /* === Helper === */
            
            .pft-absolute-center {
                position: absolute; 
                left: 50%; 
                top: 50%; 
                transform: translate(-50%, -50%);
            }

           
            /* === Bar === */
           
            .pfb-progress {
              height: 30px !important;
              vertical-align: baseline;
              display: flex;
              overflow: hidden;
              background-color: #e9ecef;
              border-radius: 0.375rem;
            }

            .pfb-progress-bar {
              display: flex;
              flex-direction: column;
              justify-content: center;
              overflow: hidden;
              text-align: center;
              white-space: nowrap;
              background-color: #e9ecef;
              transition: width 0.5s ease;
            }
            
            .pfb-progress-bar svg             { height: 66%; fill: #FFFFFF; margin-left: 5px; margin-right: 5px; }
            .pfb-progress[data-bar=in]        { margin-bottom: 15px;}
            
            .pfb-progress-bar[data-type=pv]   { background-color: var(--color-pv); }
            .pfb-progress-bar[data-type=home] { background-color: var(--color-home); }
            .pfb-progress-bar[data-type=bat]  { background-color: var(--color-bat); }
            .pfb-progress-bar[data-type=grid] { background-color: var(--color-grid); }
            .pfb-progress-bar[data-type=car]  { background-color: var(--color-car); }
            .pfb-progress-bar[data-type=heat] { background-color: var(--color-heat); }
            
        </style>`;
        document.head.innerHTML = resource + document.head.innerHTML;
    }
}