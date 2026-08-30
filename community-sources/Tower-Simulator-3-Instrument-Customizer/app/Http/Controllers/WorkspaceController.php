<?php

namespace App\Http\Controllers;

use App\Models\Airport;
use App\Models\Workspace;
use App\Support\Tower\CatalogImporter;
use Illuminate\Contracts\View\View;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\File;
use Illuminate\Validation\Rule;

class WorkspaceController extends Controller
{
    public function index(): View
    {
        $workspaces = auth()->user()
            ->workspaces()
            ->with(['airport', 'databaseVariant', 'instrumentSet', 'screens'])
            ->latest()
            ->get();

        return view('workspaces.index', [
            'workspaces' => $workspaces,
        ]);
    }

    public function create(): View
    {
        return view('workspaces.create', [
            ...$this->workspaceFormData(),
        ]);
    }

    public function store(Request $request): RedirectResponse
    {
        $validated = $this->validateWorkspace($request);

        $workspace = DB::transaction(function () use ($validated) {
            $workspace = Workspace::create([
                'public_id' => (string) str()->uuid(),
                'user_id' => auth()->id(),
                'airport_id' => $validated['airport_id'],
                'database_variant_id' => $validated['database_variant_id'],
                'instrument_set_id' => $validated['instrument_set_id'],
                'name' => $validated['name'] ?: null,
                'status' => 'draft',
            ]);

            $baseFiles = [
                'adirs' => 'adirslook.csv',
                'dbright' => 'dbrightlook.csv',
                'weather' => 'weatherlook.csv',
                'strips' => 'striplook.csv',
            ];

            foreach ($baseFiles as $screenType => $baseFileName) {
                $workspace->screens()->create([
                    'screen_type' => $screenType,
                    'base_file_name' => $baseFileName,
                    'changes_json' => [],
                ]);
            }

            return $workspace;
        });

        return redirect()
            ->route('workspaces.show', $workspace)
            ->with('status', sprintf('Workspace "%s" created.', $workspace->name ?: 'Untitled workspace'));
    }

    public function show(int $workspace): View
    {
        return view('workspaces.show', [
            'workspace' => $this->workspaceQuery()->findOrFail($workspace),
        ]);
    }

    public function edit(int $workspace): View
    {
        $workspace = $this->workspaceQuery()->findOrFail($workspace);

        return view('workspaces.edit', [
            'workspace' => $workspace,
            ...$this->workspaceFormData($workspace),
        ]);
    }

    public function update(Request $request, int $workspace): RedirectResponse
    {
        $workspace = $this->workspaceQuery()->findOrFail($workspace);
        $validated = $this->validateWorkspace($request);

        $workspace->update([
            'airport_id' => $validated['airport_id'],
            'database_variant_id' => $validated['database_variant_id'],
            'instrument_set_id' => $validated['instrument_set_id'],
            'name' => $validated['name'] ?: null,
        ]);

        return redirect()
            ->route('workspaces.show', $workspace)
            ->with('status', sprintf('Workspace "%s" updated.', $workspace->name ?: 'Untitled workspace'));
    }

    public function destroy(int $workspace): RedirectResponse
    {
        $workspace = $this->workspaceQuery()->findOrFail($workspace);
        $workspaceName = $workspace->name ?: 'Untitled workspace';

        $workspace->delete();

        return redirect()
            ->route('workspaces.index')
            ->with('status', sprintf('Workspace "%s" deleted.', $workspaceName));
    }

    protected function workspaceQuery()
    {
        return auth()->user()
            ->workspaces()
            ->with(['airport', 'databaseVariant', 'instrumentSet', 'screens']);
    }

    protected function workspaceFormData(?Workspace $workspace = null): array
    {
        $this->syncTowerCatalog();

        $airports = Airport::query()
            ->with(['databaseVariants', 'instrumentSets'])
            ->orderBy('code')
            ->get();
        $selectedAirport = $airports->firstWhere('id', (int) old('airport_id', $workspace?->airport_id))
            ?: $airports->first();

        $workspaceOptions = $airports->map(fn ($airport) => [
            'id' => $airport->id,
            'code' => $airport->code,
            'name' => $airport->name,
            'database_variants' => $airport->databaseVariants->map(fn ($variant) => [
                'id' => $variant->id,
                'name' => $variant->name,
            ])->values()->all(),
            'instrument_sets' => $airport->instrumentSets->map(fn ($set) => [
                'id' => $set->id,
                'name' => $set->name,
                'screens' => $this->screenLabelsForInstrumentSet($set),
            ])->values()->all(),
        ])->values()->all();

        return [
            'airports' => $airports,
            'selectedAirport' => $selectedAirport,
            'workspaceOptions' => $workspaceOptions,
        ];
    }

    protected function syncTowerCatalog(): void
    {
        $rootPath = config('tower.sample_airports_root');

        if (! is_string($rootPath) || ! File::isDirectory($rootPath)) {
            return;
        }

        app(CatalogImporter::class)->import($rootPath);
    }

    protected function validateWorkspace(Request $request): array
    {
        $validated = $request->validate([
            'name' => ['nullable', 'string', 'max:255'],
            'airport_id' => ['required', Rule::exists('airports', 'id')],
            'database_variant_id' => ['required', Rule::exists('database_variants', 'id')],
            'instrument_set_id' => ['required', Rule::exists('instrument_sets', 'id')],
        ]);

        $airport = Airport::query()
            ->with(['databaseVariants', 'instrumentSets'])
            ->findOrFail($validated['airport_id']);

        $databaseVariant = $airport->databaseVariants
            ->firstWhere('id', (int) $validated['database_variant_id']);
        $instrumentSet = $airport->instrumentSets
            ->firstWhere('id', (int) $validated['instrument_set_id']);

        if (! $databaseVariant) {
            return back()
                ->withErrors(['database_variant_id' => 'The selected database variant does not belong to the selected airport.'])
                ->withInput()
                ->throwResponse();
        }

        if (! $instrumentSet) {
            return back()
                ->withErrors(['instrument_set_id' => 'The selected instrument set does not belong to the selected airport.'])
                ->withInput()
                ->throwResponse();
        }

        return $validated;
    }

    protected function screenLabelsForInstrumentSet($set): array
    {
        return collect([
            $set->has_adirs ? 'ADIRS' : null,
            $set->has_dbright ? 'DBRIGHT' : null,
            $set->has_weather ? 'WEATHER' : null,
            $set->has_strips ? 'STRIPS' : null,
        ])->filter()->values()->all();
    }
}
