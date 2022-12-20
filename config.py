config = {
    'meterhub_address': 'http://192.168.0.10:8008',
    'victron_mk3_port': '/dev/serial/by-id/usb-VictronEnergy_MK3-USB_Interface_HQ2132VK4JK-if00-port0',
    'pylontech_bms_port': "/dev/serial/by-path/platform-3f980000.usb-usb-0:1.3:1.0",  # Raspberry Home (rechts oben)
    'us2000_pack_number': 2,  # number of Pylontech packs

    'password': '1234',  # Password for web access

    'http_port': 8090,  # HTTP port of the webserver
    'www_path': "www",  # path for static webserver files
    'log_path': "log",  # log path

    # the blackbox stores the specified number of records in /log/blackbox-*.jsonl in case of error
    'blackbox_size': 80,  # Number of data sets, storage time: n * 750ms

    'enable_car': True,  # Show car values on dashboard
    'enable_heat': False,  # Show heater values on dashboard

    'udc_max': 53,  # maximum voltage (only checked at BMS, MP2 has peaks ?! ToDo !!!)
    't_max': 40,  # maximum temperature

    # The setting [0] is used as default, undefined values from other settings [1, ...] are used from the setting [0]
    'setting': [
        {
            'name': 'Standard',

            'charge_min_power': 300,  # [W] lowest charge power
            'charge_max_power': 1000,  # [W] highest charge power
            'charge_reserve_power': 200,  # [W] "distance" to excess power
            'charge_end_soc': 95,  # [%] SOC at which charging is finished
            'charge_hysteresis_soc': 3,  # [%] SOC restart hysteresis
            'charge_end_voltage': 52,  # [V] Voltage at which the charge is terminated
            'charge_start_time': 30,  # [s] Time in which the start condition for the load must exist
            'charge_stop_time': 30,  # [s] Delay time in charging mode without charging

            'feed_min_power': 40,  # [W] Minimum feed power
            'feed_max_power': 2000,  # [W] Maximum feed power
            'feed_soc25_max_power': 1500,  # [W] Maximum feed power below 25% SOC
            'feed_reserve_power': 30,  # [W] "Distance" consumption to feed-in power
            'feed_end_soc': 10,  # [%] SOC at which feed-in is terminated
            'feed_hysteresis_soc': 5,  # [%] SOC restart hysteresis
            'feed_end_voltage': 47.0,  # [V] Voltage at which the feed is terminated
            'feed_start_time': 30,  # [s] Time in which the start condition for the feed must exist
            'feed_stop_time': 30,  # [s] Delay time in feed-in operation without feed-in



            'feed_throttle_time': 5 * 60,  # [s] longer feeds in one piece are limited
            'feed_throttle_power': 1500,  # [W] Performance limit with throttling

            'idle_sleep_time': 10 * 60,  # [s] Sleeptimer, (idle --> sleep) Multiplus
        },
        {
            'name': 'Maximal-Laden (Winter)',
            'charge_min_power': 200,
            'charge_max_power': 1600,
            'charge_reserve_power': 25,
            'charge_start_time': 10,
            'charge_stop_time': 5,
            'feed_soc25_max_power': 750,
        },
        {
            'name': 'Maximal-Entladen (Sommer)',
            'feed_max_power': 2400,
            'feed_reserve_power': 10,
            'feed_start_time': 10,
            'feed_stop_time': 5,
        },
        {
            'name': 'Nur Laden (Winter)',
            'charge_min_power': 200,
            'charge_max_power': 1600,
            'charge_reserve_power': 25,
            'charge_start_time': 10,
            'charge_stop_time': 5,
            'feed_end_soc': 150,     # never start feeding
        },

    ]

}
