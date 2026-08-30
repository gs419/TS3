@extends('layouts.app', ['title' => 'Register'])

@section('content')
    <section class="auth-shell">
        <article class="card auth-card">
            <span class="eyebrow">Create account</span>
            <h1>Register</h1>
            <p class="lede">Create a user account first, then manage email verification, password updates, and two-factor authentication from the account screen.</p>

            @include('auth.partials.messages')

            <form method="POST" action="{{ route('register.store') }}" class="auth-form">
                @csrf

                <label>
                    Name
                    <input type="text" name="name" value="{{ old('name') }}" required autocomplete="name">
                </label>

                <label>
                    Email address
                    <input type="email" name="email" value="{{ old('email') }}" required autocomplete="username">
                </label>

                <label>
                    Password
                    <input type="password" name="password" required autocomplete="new-password">
                </label>

                <label>
                    Confirm password
                    <input type="password" name="password_confirmation" required autocomplete="new-password">
                </label>

                <div class="auth-actions">
                    <button type="submit" class="button-link">Register</button>
                    <a class="button-link-muted" href="{{ route('login') }}">Already have an account</a>
                </div>
            </form>
        </article>
    </section>
@endsection
