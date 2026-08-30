<?php

namespace App\Support\Tower;

use App\Models\Workspace;
use App\Models\WorkspaceScreen;
use Illuminate\Support\Arr;
use Illuminate\Support\Facades\File;
use RuntimeException;

class WorkspaceAdirsService
{
    public function load(Workspace $workspace, WorkspaceScreen $screen): array
    {
        $airportPath = $this->airportFilePath($workspace);
        $lookPath = $this->lookFilePath($workspace, $screen);

        if (! File::exists($airportPath)) {
            throw new RuntimeException("Airport geometry file not found: {$airportPath}");
        }

        if (! File::exists($lookPath)) {
            throw new RuntimeException("ADIRS look file not found: {$lookPath}");
        }

        $airport = json_decode(File::get($airportPath), true, 512, JSON_THROW_ON_ERROR);
        $baseLook = $this->parseLook(File::get($lookPath));
        $changes = $this->sanitizeChanges($screen->changes_json ?? []);
        $merged = $this->mergeLook($baseLook, $changes);

        return [
            'workspace' => [
                'id' => $workspace->id,
                'name' => $workspace->name,
                'airport' => $workspace->airport?->code,
                'database' => $workspace->databaseVariant?->name,
                'instrument_set' => $workspace->instrumentSet?->name,
            ],
            'screen' => [
                'id' => $screen->id,
                'type' => $screen->screen_type,
                'base_file_name' => $screen->base_file_name,
            ],
            'airport' => [
                'icao' => Arr::get($airport, 'icao'),
                'name' => Arr::get($airport, 'name'),
                'center' => [
                    'lat' => (float) Arr::get($airport, '_centerlat', 0),
                    'lon' => (float) Arr::get($airport, '_centerlon', 0),
                ],
            ],
            'base_style_entries' => $baseLook['style_entries'],
            'style_entries' => $merged['style_entries'],
            'base_areas' => $baseLook['areas'],
            'look_source' => [
                'areas' => $merged['areas'],
            ],
            'areas' => $this->projectAreas($airport, $merged['areas']),
            'roads' => $this->roads($airport),
            'named_points' => $this->namedPoints($airport),
            'changes' => $changes,
            'stats' => [
                'roads' => count(Arr::get($airport, 'roads', [])),
                'areas' => count($merged['areas']),
                'named_points' => count($this->namedPoints($airport)),
            ],
        ];
    }

    public function sanitizeChanges(array $changes): array
    {
        $styleOverrides = collect(Arr::get($changes, 'styles', []))
            ->filter(fn ($value, $key) => is_string($key) && is_scalar($value))
            ->map(fn ($value) => trim((string) $value))
            ->filter(fn ($value) => $value !== '')
            ->all();

        $areaOverrides = collect(Arr::get($changes, 'areas', []))
            ->filter(fn ($value, $key) => is_numeric($key) && is_array($value))
            ->map(function (array $override) {
                return collect($override)
                    ->only(['color_raw'])
                    ->filter(fn ($value) => is_scalar($value) && trim((string) $value) !== '')
                    ->map(fn ($value) => trim((string) $value))
                    ->all();
            })
            ->filter(fn (array $override) => $override !== [])
            ->values()
            ->all();

        $showLabels = Arr::get($changes, 'meta.show_labels');

        return [
            'styles' => $styleOverrides,
            'areas' => $areaOverrides,
            'meta' => [
                'show_labels' => filter_var($showLabels, FILTER_VALIDATE_BOOL, FILTER_NULL_ON_FAILURE) ?? true,
            ],
        ];
    }

    protected function mergeLook(array $baseLook, array $changes): array
    {
        $styleOverrides = Arr::get($changes, 'styles', []);
        $areaOverrides = Arr::get($changes, 'areas', []);

        $styleEntries = collect($baseLook['style_entries'])
            ->map(function (array $entry) use ($styleOverrides) {
                if (array_key_exists($entry['key'], $styleOverrides)) {
                    $entry['value'] = $styleOverrides[$entry['key']];
                }

                return $entry;
            })
            ->values()
            ->all();

        $areas = collect($baseLook['areas'])
            ->map(function (array $area, int $index) use ($areaOverrides) {
                $override = $areaOverrides[$index] ?? [];
                $colorRaw = $override['color_raw'] ?? $area['color_raw'];

                return [
                    'color' => $this->rgbaString($colorRaw),
                    'color_raw' => $colorRaw,
                    'points' => $area['points'],
                ];
            })
            ->values()
            ->all();

        return [
            'style_entries' => $styleEntries,
            'areas' => $areas,
        ];
    }

    protected function airportFilePath(Workspace $workspace): string
    {
        $root = storage_path('app/tower_data/'.$workspace->airport->storage_path);
        $selectedPath = $root.'/'.$workspace->databaseVariant->relative_path.'/'.$workspace->airport->code.'.airport';
        $defaultPath = $root.'/databases/default/'.$workspace->airport->code.'.airport';

        if (File::exists($selectedPath)) {
            return $selectedPath;
        }

        return $defaultPath;
    }

    protected function lookFilePath(Workspace $workspace, WorkspaceScreen $screen): string
    {
        return storage_path('app/tower_data/'.$workspace->airport->storage_path.'/'.$workspace->instrumentSet->relative_path.'/'.$screen->base_file_name);
    }

    protected function roads(array $airport): array
    {
        return collect(Arr::get($airport, 'roads', []))
            ->map(function (array $road) {
                $points = collect(Arr::get($road, 'knots', []))
                    ->map(fn (array $knot) => [
                        'x' => (float) Arr::get($knot, 'pos.x', 0),
                        'z' => (float) Arr::get($knot, 'pos.z', 0),
                    ])
                    ->values()
                    ->all();

                $midpoint = $points !== []
                    ? $points[(int) floor((count($points) - 1) / 2)]
                    : ['x' => 0, 'z' => 0];

                return [
                    'name' => (string) Arr::get($road, 'name', ''),
                    'type' => (int) Arr::get($road, 'type', 0),
                    'width' => (float) Arr::get($road, 'width', 0),
                    'points' => $points,
                    'label' => $midpoint,
                ];
            })
            ->values()
            ->all();
    }

    protected function namedPoints(array $airport): array
    {
        return collect(Arr::get($airport, 'roads', []))
            ->flatMap(function (array $road) {
                return collect(Arr::get($road, 'knots', []))
                    ->filter(fn (array $knot) => trim((string) Arr::get($knot, 'name', '')) !== '')
                    ->map(fn (array $knot) => [
                        'road' => (string) Arr::get($road, 'name', ''),
                        'name' => (string) Arr::get($knot, 'name', ''),
                        'sayname' => (string) Arr::get($knot, 'sayname', ''),
                        'x' => (float) Arr::get($knot, 'pos.x', 0),
                        'z' => (float) Arr::get($knot, 'pos.z', 0),
                    ]);
            })
            ->values()
            ->all();
    }

    protected function parseLook(string $contents): array
    {
        $styleEntries = [];
        $areas = [];
        $lines = preg_split('/\r\n|\r|\n/', $contents) ?: [];

        for ($index = 0; $index < count($lines); $index++) {
            $line = trim($lines[$index]);

            if ($line === '') {
                continue;
            }

            if (str_starts_with($line, 'Area,"')) {
                $chunk = substr($line, 6);

                while (! str_contains($lines[$index], 'Color=') && isset($lines[$index + 1])) {
                    $index++;
                    $chunk .= "\n".$lines[$index];
                }

                preg_match('/Color=([0-9,]+)"?$/m', $chunk, $matches);
                $body = preg_replace('/Color=[0-9,]+"?$/m', '', $chunk) ?? '';
                $body = ltrim($body, '"');

                $points = collect(preg_split('/\r\n|\r|\n/', trim($body)) ?: [])
                    ->map(function (string $row) {
                        $parts = array_map('trim', explode(',', str_replace('"', '', $row)));

                        if (count($parts) < 2) {
                            return null;
                        }

                        return [
                            'lat' => (float) $parts[0],
                            'lon' => (float) $parts[1],
                        ];
                    })
                    ->filter()
                    ->values()
                    ->all();

                if (count($points) >= 3) {
                    $colorRaw = $matches[1] ?? '73,73,73,255';

                    $areas[] = [
                        'color' => $this->rgbaString($colorRaw),
                        'color_raw' => $colorRaw,
                        'points' => $points,
                    ];
                }

                continue;
            }

            $position = strpos($line, ',');

            if ($position === false) {
                continue;
            }

            $key = trim(substr($line, 0, $position));
            $value = trim(substr($line, $position + 1), '"');

            $styleEntries[] = [
                'key' => $key,
                'value' => $value,
                'kind' => preg_match('/^\d+,\d+,\d+(,\d+)?$/', $value) ? 'color' : 'value',
            ];
        }

        return [
            'style_entries' => $styleEntries,
            'areas' => $areas,
        ];
    }

    protected function projectAreas(array $airport, array $areas): array
    {
        $centerLat = (float) Arr::get($airport, '_centerlat', 0);
        $centerLon = (float) Arr::get($airport, '_centerlon', 0);
        $latRadians = deg2rad($centerLat);
        $metersPerLat = 111132.0;
        $metersPerLon = 111320.0 * cos($latRadians);

        return collect($areas)
            ->map(fn (array $area) => [
                'color' => $area['color'],
                'color_raw' => $area['color_raw'],
                'points' => collect($area['points'])
                    ->map(fn (array $point) => [
                        'x' => ($point['lon'] - $centerLon) * $metersPerLon,
                        'z' => ($point['lat'] - $centerLat) * $metersPerLat,
                    ])
                    ->values()
                    ->all(),
            ])
            ->values()
            ->all();
    }

    protected function rgbaString(string $value): string
    {
        $parts = array_map('intval', explode(',', $value));
        $red = $parts[0] ?? 255;
        $green = $parts[1] ?? 255;
        $blue = $parts[2] ?? 255;
        $alpha = ($parts[3] ?? 255) / 255;

        return sprintf('rgba(%d, %d, %d, %.3F)', $red, $green, $blue, max(0, min(1, $alpha)));
    }
}
