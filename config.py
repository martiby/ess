try:
    from config_secret import secret  # private settings (password, webhook), not in git
except ImportError:
    secret = {}

config = { 'meterhub_address': 'http://10.0.0.158:8008',
    'cycle_time': 1.0,  # [s] mainloop cycle time (regulation), synced to meterhub/AMIS ~1s
    'regulator_gain': 0.16,  # charge/feed regulator gain per cycle, power up (old fixed value: 0.12)
    'regulator_gain_down': 0.25,  # charge/feed regulator gain per cycle, power down (faster)
    'feed_grid_target': (5, 10),  # [W] target range grid import at AMIS while feeding (min, max)
    'ha_webhook_url': secret.get('ha_webhook_url', ''),  # Home Assistant, set in config_secret.py, '' = off
    'ha_interval': 5,                       # Home Assistant: send at least every x seconds
    'victron_mk3_port': '/dev/serial/by-id/usb-VictronEnergy_MK3-USB_Interface_HQ2217WWAC4-if00-port0',

    'bms_us2000': {
        'port': "/dev/serial/by-id/usb-1a86_USB_Single_Serial_556F023975-if00",  # Raspberry Home (rechts oben)
        'pack_number': 2,        # number of Pylontech packs
        'baudrate': 115200,      # Baudrate for Pylontech BMS
    },

    # 'bms_seplos': {
    #     'port': "",
    #     ...
    # },

    'batt_type': 44,      # 42=US3000, 44=US5000

    'password': secret.get('password', '1234'),  # Password for web access, set in config_secret.py

    'http_port': 8888,  # HTTP port of the webserver
    'www_path': "www",  # path for static webserver files
    'log_path': "log",  # log path

    # the blackbox stores the specified number of records in /log/blackbox-*.jsonl in case of error
    'blackbox_size': 80,  # Number of data sets, storage time: n * 750ms

    'enable_car': False,  # Show car values on dashboard
    'enable_heat': False,  # Show heater values on dashboard

    'udc_max': 54,  # maximum voltage (only checked at BMS, MP2 has peaks ?! ToDo !!!)
    't_max': 50,  # maximum temperature

    # The setting [0] is used as default, undefined values from other settings [1, ...] are used from the setting [0]
    'setting': [
        {
            'name': 'Standard',

            'charge_min_power': 100,  # [W] lowest charge power
            'charge_max_power': 1900,  # [W] highest charge power
            'charge_reserve_power': 80,  # [W] "distance" to excess power
            'charge_end_soc': 95,  # [%] SOC at which charging is finished
            'charge_hysteresis_soc': 2,  # [%] SOC restart hysteresis
            'charge_end_voltage': 53.5,  # [V] Voltage at which the charge is terminated (MP2 absorption 53.0 V)
            'charge_start_time': 2,  # [s] Time in which the start condition for the load must exist
            'charge_stop_time': 2,  # [s] Delay time in charging mode without charging

            'feed_min_power': 40,  # [W] Minimum feed power
            'feed_max_power': 2800,  # [W] Maximum feed power
            'feed_soc25_max_power': 2000,  # [W] Maximum feed power below 25% SOC
            'feed_reserve_power': 30,  # [W] "Distance" consumption to feed-in power
            'feed_end_soc': 10,  # [%] SOC at which feed-in is terminated
            'feed_hysteresis_soc': 2,  # [%] SOC restart hysteresis
            'feed_end_voltage': 47.0,  # [V] Voltage at which the feed is terminated
            'feed_start_time': 2,  # [s] Time in which the start condition for the feed must exist
            'feed_stop_time': 2,  # [s] Delay time in feed-in operation without feed-in

            'feed_throttle_time': 30 * 60,  # [s] longer feeds in one piece are limited
            'feed_throttle_power': 2000,  # [W] Performance limit with throttling
            'idle_sleep_time': 5 * 60,  # [s] Sleeptimer, (idle --> sleep) Multiplus
            'charge_night_end_soc': 0,   # [%] SOC to reach in night charge
        },
        {
            'name': 'Standard / Nacht laden',
            'charge_night_end_soc': 65,  # [%] SOC to reach in night charge
        },
        {
            'name': 'Nur Laden',
            'charge_min_power': 100,
            'charge_max_power': 1900,
            'charge_reserve_power': 80,
            'charge_start_time': 10,
            'charge_stop_time': 10,
            'feed_end_soc': 150,  # never start feeding
        },
        {
            'name': 'Nur Laden / Nacht laden',
            'charge_min_power': 100,
            'charge_max_power': 1900,
            'charge_reserve_power': 80,
            'charge_start_time': 10,
            'charge_stop_time': 10,
            'feed_end_soc': 150,  # never start feeding
            'charge_night_end_soc': 65, # [%] SOC to reach in night charge
        },
        {
            'name': 'Winter / 25% Reserve',
            'charge_min_power': 100,
            'charge_max_power': 1900,
            'charge_reserve_power': 80,
            'charge_start_time': 10,
            'charge_stop_time': 10,
            'feed_soc25_max_power': 2000,
            'feed_max_power': 2800,  # [W] Maximum feed power
            'feed_reserve_power': 30,  # [W] "Distance" consumption to feed-in power
            'feed_end_soc': 25,  # [%] SOC at which feed-in is terminated
            'feed_hysteresis_soc': 2,  # [%] SOC restart hysteresis
            'charge_night_end_soc': 0,
        },
        {
            'name': 'Winter / 25% Reserve / Nacht laden',
            'charge_min_power': 100,
            'charge_max_power': 1900,
            'charge_reserve_power': 80,
            'charge_start_time': 10,
            'charge_stop_time': 10,
            'feed_soc25_max_power': 2000,
            'feed_max_power': 2800,  # [W] Maximum feed power
            'feed_reserve_power': 30,  # [W] "Distance" consumption to feed-in power
            'feed_end_soc': 25,  # [%] SOC at which feed-in is terminated
            'feed_hysteresis_soc': 2,  # [%] SOC restart hysteresis
            'charge_night_end_soc': 65, # [%] SOC to reach in night charge
        },
        {
            'name': 'Laden bis 100%',
            'charge_end_soc': 105,  # [%] SOC at which charging is finished
        },
        {   'name': 'Laden max 500W',
            'charge_max_power': 500,
        }
    ],

    # enable csv log
    #'csv_log': {'interval': 60,   # storage interval in seconds
    #            'columns': [      # first entry is the name, second and so on the route inside main dataset /api/state
    #                ('time', 'ess', 'time'),
    #                ('state', 'ess', 'state'),
    #                ('bat_ac_p', 'meterhub', 'bat_p'),
    #                ('mp2_bat_u', 'multiplus', 'bat_u'),
    #                ('mp2_bat_i', 'multiplus', 'bat_i'),
    #                ('bms_u0', 'bms', 'pack_u', 0),
    #                ('bms_u1', 'bms', 'pack_u', 1),
    #                ('bms_i0', 'bms', 'pack_i', 0),
    #                ('bms_i1', 'bms', 'pack_i', 1),
    #                ('bms_soc0', 'bms', 'pack_soc', 0),
    #                ('bms_soc1', 'bms', 'pack_soc', 1)]},

}
