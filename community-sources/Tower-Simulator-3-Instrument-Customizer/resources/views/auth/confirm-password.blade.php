@extends('layouts.app', ['title' => 'Confirm password'])

@section('content')
    <section class="auth-shell">
        <article class="card auth-card">
            <span class="eyebrow">Confirm password</span>
            <h1>Re-enter your password</h1>
            <p class="lede">Fortify requires a recent password confirmation before changing sensitive security settings such as two-factor authentication.</p>

            @include('auth.partials.messages')

            <form method="POST" action="{{ route('password.confirm.store') }}" class="auth-form">
                @csrf

                <label>
                    Current password
                    <input type="password" name="password" required autocomplete="current-password">
                </label>

                <div class="auth-actions">
                    <button type="submit" class="button-link">Confirm password</button>
                    <a class="button-link-muted" href="{{ route('account') }}">Back to account</a>
                </div>
            </form>
        </article>
    </section>
@endsection
