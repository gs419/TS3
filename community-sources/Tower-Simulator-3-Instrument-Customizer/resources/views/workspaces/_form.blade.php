<section class="card workspace-form-card" data-workspace-form>
    <script type="application/json" data-workspace-options>@json($workspaceOptions)</script>

    @if ($airports->isEmpty())
        <div class="workspace-empty-state">
            <h2>No source data imported yet</h2>
            <p>
                Workspaces depend on airport, database variant, and instrument set records. The form stays disabled until the
                `tower_data` catalog has been imported into the app database.
            </p>
        </div>
    @endif

    <form method="POST" action="{{ $action }}" class="auth-form workspace-form">
        @csrf
        @isset($method)
            @method($method)
        @endisset

        <div class="workspace-form-grid">
            <label class="workspace-form-span">
                Workspace name
                <input
                    type="text"
                    name="name"
                    value="{{ old('name', $workspace->name ?? '') }}"
                    placeholder="KLAX Noon set"
                    maxlength="255"
                >
            </label>

            <label>
                Airport
                <select name="airport_id" data-workspace-airport required @disabled($airports->isEmpty())>
                    <option value="">Select an airport</option>
                    @foreach ($airports as $airport)
                        <option
                            value="{{ $airport->id }}"
                            @selected(
                                (string) old('airport_id', $selectedAirport?->id ?? $workspace->airport_id ?? null) === (string) $airport->id
                            )
                        >
                            {{ $airport->code }}@if ($airport->name) · {{ $airport->name }}@endif
                        </option>
                    @endforeach
                </select>
            </label>

            <label>
                Base database variant
                <select
                    name="database_variant_id"
                    data-workspace-database
                    data-selected="{{ old('database_variant_id', $workspace->database_variant_id ?? $selectedAirport?->databaseVariants->first()?->id) }}"
                    required
                    @disabled($airports->isEmpty())
                >
                    @forelse ($selectedAirport?->databaseVariants ?? [] as $variant)
                        <option
                            value="{{ $variant->id }}"
                            @selected(
                                (string) old('database_variant_id', $workspace->database_variant_id ?? $selectedAirport?->databaseVariants->first()?->id) === (string) $variant->id
                            )
                        >
                            {{ $variant->name }}
                        </option>
                    @empty
                        <option value="">No options available</option>
                    @endforelse
                </select>
            </label>

            <label>
                Base instrument set
                <select
                    name="instrument_set_id"
                    data-workspace-set
                    data-selected="{{ old('instrument_set_id', $workspace->instrument_set_id ?? $selectedAirport?->instrumentSets->first()?->id) }}"
                    required
                    @disabled($airports->isEmpty())
                >
                    @forelse ($selectedAirport?->instrumentSets ?? [] as $set)
                        <option
                            value="{{ $set->id }}"
                            @selected(
                                (string) old('instrument_set_id', $workspace->instrument_set_id ?? $selectedAirport?->instrumentSets->first()?->id) === (string) $set->id
                            )
                        >
                            {{ $set->name }}
                        </option>
                    @empty
                        <option value="">No options available</option>
                    @endforelse
                </select>
            </label>
        </div>

        <div class="workspace-create-summary" data-workspace-summary>
            Select an airport to see which database variants and instrument sets are available.
        </div>

        <div class="auth-actions">
            <button type="submit" class="button-link">{{ $submitLabel }}</button>
            <a class="button-link-muted" href="{{ $cancelRoute }}">Back to overview</a>
        </div>
    </form>
</section>
