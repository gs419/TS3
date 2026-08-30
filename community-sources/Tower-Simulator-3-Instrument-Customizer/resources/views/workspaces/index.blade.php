@extends('layouts.app', ['title' => 'Workspaces'])

@section('content')
    <section class="card hero-card">
        <p class="eyebrow">Workspaces</p>
        <h1>Your workspace overview</h1>
        <p class="lede">
            Each workspace ties together one airport, one database variant, one instrument set, and the per-screen customizations that belong to that combination.
        </p>

        <div class="auth-actions">
            <a class="button-link" href="{{ route('workspaces.create') }}">Create workspace</a>
        </div>
    </section>

    @if ($workspaces->isEmpty())
        <section class="card">
            <h2>No workspaces yet</h2>
            <p class="settings-copy">
                You do not have any saved workspaces yet. The next step is creating the first workspace creation flow on top of the new base data structure.
            </p>
        </section>
    @else
        <section class="workspace-grid">
            @foreach ($workspaces as $workspace)
                <article class="card workspace-card">
                    <div class="workspace-head">
                        <div>
                            <h2>{{ $workspace->name ?: 'Untitled workspace' }}</h2>
                            <p class="workspace-meta">
                                {{ $workspace->airport?->code }}
                                @if ($workspace->databaseVariant)
                                    · {{ $workspace->databaseVariant->name }}
                                @endif
                                @if ($workspace->instrumentSet)
                                    · {{ $workspace->instrumentSet->name }}
                                @endif
                            </p>
                        </div>

                        <span class="workspace-status">{{ $workspace->status }}</span>
                    </div>

                    <dl class="workspace-stats">
                        <div>
                            <dt>Airport</dt>
                            <dd>{{ $workspace->airport?->code ?? 'Unknown' }}</dd>
                        </div>
                        <div>
                            <dt>Database</dt>
                            <dd>{{ $workspace->databaseVariant?->name ?? 'Unknown' }}</dd>
                        </div>
                        <div>
                            <dt>Instrument set</dt>
                            <dd>{{ $workspace->instrumentSet?->name ?? 'Unknown' }}</dd>
                        </div>
                        <div>
                            <dt>Screens</dt>
                            <dd>{{ $workspace->screens->count() }}</dd>
                        </div>
                    </dl>

                    <p class="workspace-foot">
                        Updated {{ $workspace->updated_at?->diffForHumans() ?? 'recently' }}
                    </p>

                    <div class="auth-actions">
                        <a class="button-link" href="{{ route('workspaces.show', $workspace) }}">Open workspace</a>
                        <a class="button-link-muted" href="{{ route('workspaces.edit', $workspace) }}">Edit</a>
                    </div>
                </article>
            @endforeach
        </section>
    @endif
@endsection
