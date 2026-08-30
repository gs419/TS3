@extends('layouts.app', ['title' => 'TS3IC'])

@section('content')
    <section class="card hero-card">
        <p class="eyebrow">Authentication baseline</p>
        <h1>Fortify screens are the first rebuild step</h1>
        <p class="lede">
            Registration, login, password reset, email verification, password confirmation, account settings, and two-factor authentication are wired from the clean reset baseline.
        </p>

        <div class="auth-actions">
            @auth
                <a class="button-link" href="{{ route('account') }}">Open account settings</a>
            @else
                <a class="button-link" href="{{ route('login') }}">Log in</a>
                <a class="button-link-muted" href="{{ route('register') }}">Create account</a>
            @endauth
        </div>
    </section>

    <section class="card">
        <h2>Reference note</h2>
        <p>
            The recovered Tower data and canvas rendering notes are still preserved in
            <code>docs/tower-data-and-rendering-notes.md</code>.
        </p>
    </section>
@endsection
