@extends('layouts.app', ['title' => 'Verify email'])

@section('content')
    <section class="auth-shell">
        <article class="card auth-card">
            <span class="eyebrow">Verify email</span>
            <h1>Check your inbox</h1>
            <p class="lede">
                Before continuing, verify your email address using the link we sent you. If you did not receive it, request another one below.
            </p>

            @include('auth.partials.messages')

            <form method="POST" action="{{ route('verification.send') }}" class="auth-form">
                @csrf

                <div class="auth-actions">
                    <button type="submit" class="button-link">Resend verification email</button>
                    <a class="button-link-muted" href="{{ route('account') }}">Go to account</a>
                </div>
            </form>
        </article>
    </section>
@endsection
