@extends('layouts.app', ['title' => 'Edit Workspace'])

@section('content')
    <section class="card hero-card">
        <p class="eyebrow">Workspaces</p>
        <h1>Edit workspace</h1>
        <p class="lede">
            Update the airport, base database variant, shared instrument set, and workspace name for this draft.
        </p>
    </section>

    @include('auth.partials.messages')

    @include('workspaces._form', [
        'workspace' => $workspace,
        'action' => route('workspaces.update', $workspace),
        'method' => 'PUT',
        'submitLabel' => 'Save workspace',
        'cancelRoute' => route('workspaces.show', $workspace),
    ])
@endsection
