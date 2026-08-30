@extends('layouts.app', ['title' => 'Log in'])

@section('content')
    <section class="auth-shell">
        <article class="card auth-card">
            <span class="eyebrow">Account access</span>
            <h1>Log in</h1>
            <p class="lede">Use your email and password to continue to your account settings and security controls.</p>

            @include('auth.partials.messages')

            <form method="POST" action="{{ route('login.store') }}" class="auth-form">
                @csrf

                <label>
                    Email address
                    <input type="email" name="email" value="{{ old('email') }}" required autofocus autocomplete="username">
                </label>

                <label>
                    Password
                    <input type="password" name="password" required autocomplete="current-password">
                </label>

                <label class="checkline">
                    <input type="checkbox" name="remember">
                    Keep me signed in
                </label>

                <div class="auth-actions">
                    <button type="submit" class="button-link">Log in</button>
                    <a class="button-link-muted" href="{{ route('password.request') }}">Forgot password</a>
                </div>
            </form>
        </article>
    </section>
@endsection
