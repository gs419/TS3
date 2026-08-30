<?php

namespace App\Support\Tower;

use App\Models\Airport;
use App\Models\DatabaseVariant;
use App\Models\InstrumentSet;
use Illuminate\Support\Facades\File;
use InvalidArgumentException;

class CatalogImporter
{
    public function import(string $rootPath): array
    {
        if (! File::isDirectory($rootPath)) {
            throw new InvalidArgumentException("Tower data path does not exist: {$rootPath}");
        }

        $summary = [
            'airports_created' => 0,
            'database_variants_created' => 0,
            'instrument_sets_created' => 0,
            'skipped_airports' => [],
        ];

        foreach (File::directories($rootPath) as $airportPath) {
            $icao = basename($airportPath);
            $defaultAirportFile = $airportPath.'/databases/default/'.$icao.'.airport';

            if (! File::exists($defaultAirportFile)) {
                $summary['skipped_airports'][] = $icao;

                continue;
            }

            $airport = Airport::firstOrCreate(
                ['code' => $icao],
                [
                    'name' => null,
                    'storage_path' => $icao,
                ],
            );

            if ($airport->wasRecentlyCreated) {
                $summary['airports_created']++;
            }

            $summary['database_variants_created'] += $this->importDatabaseVariants($airport, $airportPath, $icao);
            $summary['instrument_sets_created'] += $this->importInstrumentSets($airport, $airportPath);
        }

        sort($summary['skipped_airports']);

        return $summary;
    }

    protected function importDatabaseVariants(Airport $airport, string $airportPath, string $icao): int
    {
        $created = 0;
        $databasesPath = $airportPath.'/databases';

        if (! File::isDirectory($databasesPath)) {
            return $created;
        }

        foreach (File::directories($databasesPath) as $variantPath) {
            $variantName = basename($variantPath);
            $relativePath = 'databases/'.$variantName;
            $airportFileRelativePath = $relativePath.'/'.$icao.'.airport';
            $hasOwnGeometry = File::exists($variantPath.'/'.$icao.'.airport');

            $variant = DatabaseVariant::firstOrCreate(
                [
                    'airport_id' => $airport->id,
                    'name' => $variantName,
                ],
                [
                    'relative_path' => $relativePath,
                    'airport_file_relative_path' => $hasOwnGeometry ? $airportFileRelativePath : null,
                    'uses_default_airport_geometry' => ! $hasOwnGeometry,
                ],
            );

            if ($variant->wasRecentlyCreated) {
                $created++;
            }
        }

        return $created;
    }

    protected function importInstrumentSets(Airport $airport, string $airportPath): int
    {
        $created = 0;
        $instrumentsPath = $airportPath.'/instruments';

        if (! File::isDirectory($instrumentsPath)) {
            return $created;
        }

        foreach (File::directories($instrumentsPath) as $setPath) {
            $setName = basename($setPath);
            $relativePath = 'instruments/'.$setName;

            $instrumentSet = InstrumentSet::firstOrCreate(
                [
                    'airport_id' => $airport->id,
                    'name' => $setName,
                ],
                [
                    'relative_path' => $relativePath,
                    'has_adirs' => File::exists($setPath.'/adirslook.csv'),
                    'has_dbright' => File::exists($setPath.'/dbrightlook.csv'),
                    'has_weather' => File::exists($setPath.'/weatherlook.csv'),
                    'has_strips' => File::exists($setPath.'/striplook.csv'),
                ],
            );

            if ($instrumentSet->wasRecentlyCreated) {
                $created++;
            }
        }

        return $created;
    }
}
