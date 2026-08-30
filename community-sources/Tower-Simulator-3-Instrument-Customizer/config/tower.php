<?php

return [
    'sample_airports_root' => env(
        'TOWER_SAMPLE_AIRPORTS_ROOT',
        storage_path('app/tower_data')
    ),
];
