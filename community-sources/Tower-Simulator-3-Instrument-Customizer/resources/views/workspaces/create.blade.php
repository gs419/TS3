@extends('layouts.app', ['title' => 'Create Workspace'])

@section('content')
    <section class="card hero-card">
        <p class="eyebrow">Workspaces</p>
        <h1>Create a workspace</h1>
        <p class="lede">
            Choose the airport, base database variant, and shared instrument set that should define the starting point for ADIRS, DBRIGHT, WEATHER, and STRIPS.
        </p>
    </section>

    @include('auth.partials.messages')

    @include('workspaces._form', [
        'workspace' => null,
        'action' => route('workspaces.store'),
        'submitLabel' => 'Create workspace',
        'cancelRoute' => route('workspaces.index'),
    ])
@endsection
