@extends('layouts.app', ['title' => $workspace->name ?: 'Workspace'])

@section('content')
    <section class="card hero-card">
        <p class="eyebrow">Workspaces</p>
        <h1>{{ $workspace->name ?: 'Untitled workspace' }}</h1>
        <p class="lede">
            This workspace ties one airport, one database variant, and one instrument set to the screen customizations stored for the current user.
        </p>

        <div class="auth-actions">
            <a class="button-link" href="{{ route('workspaces.edit', $workspace) }}">Edit workspace</a>
            <a class="button-link-muted" href="{{ route('workspaces.index') }}">Back to overview</a>
            <form method="POST" action="{{ route('workspaces.destroy', $workspace) }}">
                @csrf
                @method('DELETE')

                <button type="submit" class="button-link-muted">Delete workspace</button>
            </form>
        </div>
    </section>

    @include('auth.partials.messages')

    <section class="workspace-detail-grid">
        <article class="card workspace-card">
            <div class="workspace-head">
                <div>
                    <h2>Workspace details</h2>
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
        </article>

        <article class="card workspace-card">
            <h2>Screen bases</h2>
            <p class="settings-copy">
                These are the screen records currently attached to the workspace. Each screen will get both a sidebar editor and a multiwindow editor as the rebuild continues.
            </p>

            <dl class="workspace-screen-list">
                @foreach ($workspace->screens->sortBy('screen_type') as $screen)
                    <div class="workspace-screen-row">
                        <div>
                            <dt>{{ strtoupper($screen->screen_type) }}</dt>
                            <dd>{{ $screen->base_file_name }}</dd>
                        </div>

                        <div class="workspace-screen-actions">
                            @if ($screen->screen_type === 'adirs')
                                <a class="button-link" href="{{ route('workspaces.screens.adirs.edit', $workspace) }}">Sidebar edit</a>
                            @else
                                <span class="button-link is-disabled" aria-disabled="true">Sidebar edit</span>
                            @endif
                            <span class="button-link-muted is-disabled" aria-disabled="true">Multiwindow edit</span>
                        </div>
                    </div>
                @endforeach
            </dl>
        </article>
    </section>
@endsection
