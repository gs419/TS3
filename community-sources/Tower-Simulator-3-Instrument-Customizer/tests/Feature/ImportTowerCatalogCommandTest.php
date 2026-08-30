<?php

namespace Tests\Feature;

use App\Models\Airport;
use App\Models\DatabaseVariant;
use App\Models\InstrumentSet;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\File;
use Tests\TestCase;

class ImportTowerCatalogCommandTest extends TestCase
{
    use RefreshDatabase;

    protected string $catalogPath;

    protected function setUp(): void
    {
        parent::setUp();

        $this->catalogPath = storage_path('app/testing/tower_data_import');

        File::deleteDirectory($this->catalogPath);
        File::ensureDirectoryExists($this->catalogPath);
    }

    protected function tearDown(): void
    {
        File::deleteDirectory($this->catalogPath);

        parent::tearDown();
    }

    public function test_it_imports_missing_airports_database_variants_and_instrument_sets(): void
    {
        $this->makeFile('KLAX/databases/default/KLAX.airport');
        $this->makeFile('KLAX/databases/default/airlines.csv');
        $this->makeFile('KLAX/databases/real-ops/airlines.csv');
        $this->makeFile('KLAX/instruments/default/adirslook.csv');
        $this->makeFile('KLAX/instruments/default/dbrightlook.csv');
        $this->makeFile('KLAX/instruments/default/striplook.csv');
        $this->makeFile('KLAX/instruments/weather-only/weatherlook.csv');
        $this->makeFile('KSEA/databases/default/airlines.csv');
        $this->makeFile('KSEA/instruments/default/adirslook.csv');

        $this->artisan('tower:import-catalog', ['--path' => $this->catalogPath])
            ->expectsOutputToContain('Created 1 airport(s), 2 database variant(s), and 2 instrument set(s).')
            ->expectsOutputToContain('Skipped airports without a default geometry file: KSEA')
            ->assertExitCode(0);

        $this->assertDatabaseHas('airports', [
            'code' => 'KLAX',
            'storage_path' => 'KLAX',
        ]);
        $this->assertDatabaseMissing('airports', [
            'code' => 'KSEA',
        ]);

        $airport = Airport::query()->where('code', 'KLAX')->firstOrFail();

        $this->assertDatabaseHas('database_variants', [
            'airport_id' => $airport->id,
            'name' => 'default',
            'relative_path' => 'databases/default',
            'airport_file_relative_path' => 'databases/default/KLAX.airport',
            'uses_default_airport_geometry' => false,
        ]);
        $this->assertDatabaseHas('database_variants', [
            'airport_id' => $airport->id,
            'name' => 'real-ops',
            'relative_path' => 'databases/real-ops',
            'airport_file_relative_path' => null,
            'uses_default_airport_geometry' => true,
        ]);
        $this->assertDatabaseHas('instrument_sets', [
            'airport_id' => $airport->id,
            'name' => 'default',
            'relative_path' => 'instruments/default',
            'has_adirs' => true,
            'has_dbright' => true,
            'has_weather' => false,
            'has_strips' => true,
        ]);
        $this->assertDatabaseHas('instrument_sets', [
            'airport_id' => $airport->id,
            'name' => 'weather-only',
            'relative_path' => 'instruments/weather-only',
            'has_adirs' => false,
            'has_dbright' => false,
            'has_weather' => true,
            'has_strips' => false,
        ]);
    }

    public function test_it_only_creates_missing_rows_and_keeps_existing_catalog_entries(): void
    {
        $airport = Airport::create([
            'code' => 'KLAX',
            'name' => 'Existing airport name',
            'storage_path' => 'custom-storage-path',
        ]);
        DatabaseVariant::create([
            'airport_id' => $airport->id,
            'name' => 'default',
            'relative_path' => 'legacy/path',
            'airport_file_relative_path' => null,
            'uses_default_airport_geometry' => true,
        ]);
        InstrumentSet::create([
            'airport_id' => $airport->id,
            'name' => 'default',
            'relative_path' => 'legacy/instruments',
            'has_adirs' => false,
            'has_dbright' => false,
            'has_weather' => false,
            'has_strips' => false,
        ]);

        $this->makeFile('KLAX/databases/default/KLAX.airport');
        $this->makeFile('KLAX/databases/nightly/airlines.csv');
        $this->makeFile('KLAX/instruments/default/adirslook.csv');
        $this->makeFile('KLAX/instruments/default/dbrightlook.csv');
        $this->makeFile('KLAX/instruments/default/striplook.csv');
        $this->makeFile('KLAX/instruments/modern/adirslook.csv');

        $this->artisan('tower:import-catalog', ['--path' => $this->catalogPath])
            ->expectsOutputToContain('Created 0 airport(s), 1 database variant(s), and 1 instrument set(s).')
            ->assertExitCode(0);

        $airport->refresh();

        $this->assertSame('Existing airport name', $airport->name);
        $this->assertSame('custom-storage-path', $airport->storage_path);

        $existingVariant = DatabaseVariant::query()
            ->where('airport_id', $airport->id)
            ->where('name', 'default')
            ->firstOrFail();
        $existingSet = InstrumentSet::query()
            ->where('airport_id', $airport->id)
            ->where('name', 'default')
            ->firstOrFail();

        $this->assertSame('legacy/path', $existingVariant->relative_path);
        $this->assertNull($existingVariant->airport_file_relative_path);
        $this->assertTrue($existingVariant->uses_default_airport_geometry);
        $this->assertSame('legacy/instruments', $existingSet->relative_path);
        $this->assertFalse($existingSet->has_adirs);
        $this->assertFalse($existingSet->has_dbright);
        $this->assertFalse($existingSet->has_strips);

        $this->assertDatabaseHas('database_variants', [
            'airport_id' => $airport->id,
            'name' => 'nightly',
            'relative_path' => 'databases/nightly',
            'uses_default_airport_geometry' => true,
        ]);
        $this->assertDatabaseHas('instrument_sets', [
            'airport_id' => $airport->id,
            'name' => 'modern',
            'relative_path' => 'instruments/modern',
            'has_adirs' => true,
            'has_dbright' => false,
            'has_weather' => false,
            'has_strips' => false,
        ]);

        $this->assertSame(2, DatabaseVariant::query()->where('airport_id', $airport->id)->count());
        $this->assertSame(2, InstrumentSet::query()->where('airport_id', $airport->id)->count());
    }

    protected function makeFile(string $relativePath, string $contents = 'test'): void
    {
        $path = $this->catalogPath.'/'.$relativePath;

        File::ensureDirectoryExists(dirname($path));
        File::put($path, $contents);
    }
}
