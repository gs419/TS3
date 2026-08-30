@extends('layouts.app', ['title' => 'Forgot password'])

@section('content')
    <section class="auth-shell">
        <article class="card auth-card">
            <span class="eyebrow">Password reset</span>
            <h1>Request a reset link</h1>
            <p class="lede">Enter your email address and Fortify will send you a password reset link.</p>

            @include('auth.partials.messages')

            <form method="POST" action="{{ route('password.email') }}" class="auth-form">
                @csrf

                <label>
                    Email address
                    <input type="email" name="email" value="{{ old('email') }}" required autocomplete="username">
                </label>

                <div class="auth-actions">
                    <button type="submit" class="button-link">Send reset link</button>
                    <a class="button-link-muted" href="{{ route('login') }}">Back to login</a>
                </div>
            </form>
        </article>
    </section>
@endsection
