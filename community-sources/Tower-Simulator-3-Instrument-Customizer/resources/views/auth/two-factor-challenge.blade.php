@extends('layouts.app', ['title' => 'Two-factor challenge'])

@section('content')
    <section class="auth-shell">
        <article class="card auth-card">
            <span class="eyebrow">Two-factor login</span>
            <h1>Complete the second step</h1>
            <p class="lede">Enter the authentication code from your authenticator app or use one of your recovery codes.</p>

            @include('auth.partials.messages')

            <form method="POST" action="{{ route('two-factor.login.store') }}" class="auth-form">
                @csrf

                <label>
                    Authentication code
                    <input type="text" name="code" inputmode="numeric" autocomplete="one-time-code" autofocus>
                </label>

                <p class="auth-divider">or</p>

                <label>
                    Recovery code
                    <input type="text" name="recovery_code" autocomplete="one-time-code">
                </label>

                <div class="auth-actions">
                    <button type="submit" class="button-link">Continue</button>
                    <a class="button-link-muted" href="{{ route('login') }}">Back to login</a>
                </div>
            </form>
        </article>
    </section>
@endsection
