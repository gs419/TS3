<?php

use App\Support\Tower\CatalogImporter;
use Illuminate\Foundation\Inspiring;
use Illuminate\Support\Facades\Artisan;

Artisan::command('inspire', function () {
    $this->comment(Inspiring::quote());
})->purpose('Display an inspiring quote');

Artisan::command('tower:import-catalog {--path=}', function (CatalogImporter $importer) {
    $path = $this->option('path') ?: config('tower.sample_airports_root');
    $summary = $importer->import($path);

    $this->info(sprintf(
        'Created %d airport(s), %d database variant(s), and %d instrument set(s).',
        $summary['airports_created'],
        $summary['database_variants_created'],
        $summary['instrument_sets_created'],
    ));

    if ($summary['skipped_airports'] !== []) {
        $this->warn(
            'Skipped airports without a default geometry file: '.implode(', ', $summary['skipped_airports'])
        );
    }
})->purpose('Import missing airport, database variant, and instrument set catalog rows from tower_data');
