@extends('layouts.app', ['title' => 'ADIRS Editor'])

@section('content')
    <section class="card hero-card">
        <p class="eyebrow">ADIRS</p>
        <h1>{{ $workspace->name ?: 'Untitled workspace' }}</h1>
        <p class="lede">
            Edit the ADIRS styling for this workspace using the selected airport geometry, database variant, and instrument set as the base.
        </p>

        <div class="auth-actions">
            <button type="submit" form="adirs-editor-form" class="button-link">Save ADIRS changes</button>
            <a class="button-link-muted" href="{{ route('workspaces.show', $workspace) }}">Back to workspace</a>
            <span class="button-link-muted is-disabled" aria-disabled="true">Multiwindow edit</span>
        </div>
    </section>

    @include('auth.partials.messages')

    <section
        class="adirs-layout"
        data-adirs-viewer
        data-adirs-payload='@json($payload)'
    >
        <article class="card adirs-canvas-card">
            <div class="workspace-head">
                <div>
                    <h2>Live preview</h2>
                    <p class="workspace-meta">
                        {{ $workspace->airport?->code }}
                        · {{ $workspace->databaseVariant?->name }}
                        · {{ $workspace->instrumentSet?->name }}
                    </p>
                </div>

                <label class="checkline">
                    <input type="checkbox" data-adirs-labels @checked($payload['changes']['meta']['show_labels'] ?? true)>
                    Show labels
                </label>
            </div>

            <canvas class="adirs-canvas" data-adirs-canvas></canvas>

            <dl class="workspace-stats" data-adirs-stats></dl>
        </article>

        <article class="card adirs-sidebar-card">
            <form method="POST" action="{{ route('workspaces.screens.adirs.update', $workspace) }}" id="adirs-editor-form" class="auth-form">
                @csrf
                @method('PUT')
                <input
                    type="hidden"
                    name="changes_json"
                    data-adirs-changes-input
                    value="{{ e(json_encode($payload['changes'], JSON_THROW_ON_ERROR)) }}"
                >

                <div class="auth-actions">
                    <button type="submit" class="button-link">Save ADIRS changes</button>
                    <button type="button" class="button-link-muted" data-adirs-reset>Reset to base</button>
                </div>

                <div class="workspace-create-summary" data-adirs-status>
                    Loaded {{ $payload['workspace']['airport'] }} with {{ $payload['workspace']['database'] }} and {{ $payload['workspace']['instrument_set'] }}.
                </div>

                <div class="adirs-editor-tabs" data-adirs-editor-tabs></div>
                <div class="adirs-editor" data-adirs-editor></div>
                <div class="adirs-areas" data-adirs-areas></div>
            </form>
        </article>
    </section>
@endsection
