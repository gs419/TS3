@extends('layouts.app', ['title' => 'Reset password'])

@section('content')
    <section class="auth-shell">
        <article class="card auth-card">
            <span class="eyebrow">Password reset</span>
            <h1>Set a new password</h1>
            <p class="lede">Complete the reset flow by choosing a new password for the account tied to the reset email.</p>

            @include('auth.partials.messages')

            <form method="POST" action="{{ route('password.update') }}" class="auth-form">
                @csrf

                <input type="hidden" name="token" value="{{ $request->route('token') }}">

                <label>
                    Email address
                    <input type="email" name="email" value="{{ old('email', $request->email) }}" required autocomplete="username">
                </label>

                <label>
                    New password
                    <input type="password" name="password" required autocomplete="new-password">
                </label>

                <label>
                    Confirm new password
                    <input type="password" name="password_confirmation" required autocomplete="new-password">
                </label>

                <div class="auth-actions">
                    <button type="submit" class="button-link">Reset password</button>
                    <a class="button-link-muted" href="{{ route('login') }}">Back to login</a>
                </div>
            </form>
        </article>
    </section>
@endsection
