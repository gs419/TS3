@extends('layouts.app', ['title' => 'Account'])

@section('content')
    <section class="card hero-card">
        <p class="eyebrow">Account</p>
        <h1>Security and profile settings</h1>
        <p class="lede">
            Manage your identity, password, email verification, and two-factor authentication from one place.
        </p>
    </section>

    @include('auth.partials.messages')

    <section
        class="settings-grid"
        data-two-factor-root
        data-enabled="{{ auth()->user()->two_factor_secret ? 'true' : 'false' }}"
        data-confirmed="{{ auth()->user()->two_factor_confirmed_at ? 'true' : 'false' }}"
        data-qr-url="{{ route('two-factor.qr-code') }}"
        data-secret-url="{{ route('two-factor.secret-key') }}"
        data-recovery-url="{{ route('two-factor.recovery-codes') }}"
    >
        @if ($canUpdateProfile)
            <article class="card settings-card">
                <h2>Profile</h2>
                <p class="settings-copy">Update your display name and email address.</p>

                <form method="POST" action="{{ route('user-profile-information.update') }}" class="auth-form">
                    @csrf
                    @method('PUT')

                    <label>
                        Name
                        <input type="text" name="name" value="{{ old('name', auth()->user()->name) }}" required autocomplete="name">
                    </label>

                    <label>
                        Email address
                        <input type="email" name="email" value="{{ old('email', auth()->user()->email) }}" required autocomplete="username">
                    </label>

                    <div class="auth-actions">
                        <button type="submit" class="button-link">Save profile</button>
                    </div>
                </form>
            </article>
        @endif

        @if ($canUpdatePassword)
            <article class="card settings-card">
                <h2>Password</h2>
                <p class="settings-copy">Change your password using your current password as confirmation.</p>

                <form method="POST" action="{{ route('user-password.update') }}" class="auth-form">
                    @csrf
                    @method('PUT')

                    <label>
                        Current password
                        <input type="password" name="current_password" required autocomplete="current-password">
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
                        <button type="submit" class="button-link">Update password</button>
                    </div>
                </form>
            </article>
        @endif

        @if ($canVerifyEmail)
            <article class="card settings-card">
                <h2>Email verification</h2>
                @if (auth()->user()->hasVerifiedEmail())
                    <p class="auth-message auth-message-success">Your email address is verified.</p>
                @else
                    <p class="settings-copy">
                        Your email address is not verified yet. Use the button below to send a fresh verification link.
                    </p>

                    <form method="POST" action="{{ route('verification.send') }}" class="auth-form">
                        @csrf

                        <div class="auth-actions">
                            <button type="submit" class="button-link">Send verification email</button>
                        </div>
                    </form>
                @endif
            </article>
        @endif

        @if ($canManageTwoFactor)
            <article class="card settings-card settings-card-wide">
                <h2>Two-factor authentication</h2>
                <p class="settings-copy">
                    Add an authenticator app for a second login factor. This flow uses Fortify's built-in QR code, recovery codes, and confirmation step.
                </p>

                @if (! auth()->user()->two_factor_secret)
                    <form method="POST" action="{{ route('two-factor.enable') }}" class="auth-form">
                        @csrf

                        <div class="auth-actions">
                            <button type="submit" class="button-link">Enable two-factor authentication</button>
                        </div>
                    </form>
                @else
                    <div class="two-factor-grid">
                        <div class="two-factor-panel">
                            <h3>Setup</h3>
                            <div class="two-factor-qr" data-two-factor-qr>QR code will appear here after setup data loads.</div>
                            <p class="two-factor-secret" data-two-factor-secret></p>
                        </div>

                        <div class="two-factor-panel">
                            @if (! auth()->user()->two_factor_confirmed_at)
                                <h3>Confirm app code</h3>
                                <p class="settings-copy">Scan the QR code, then enter the six-digit code from your authenticator app.</p>

                                <form method="POST" action="{{ route('two-factor.confirm') }}" class="auth-form">
                                    @csrf

                                    <label>
                                        Authentication code
                                        <input type="text" name="code" inputmode="numeric" autocomplete="one-time-code" required>
                                    </label>

                                    <div class="auth-actions">
                                        <button type="submit" class="button-link">Confirm two-factor</button>
                                    </div>
                                </form>
                            @else
                                <h3>Recovery codes</h3>
                                <p class="settings-copy">Store these codes somewhere safe. Each code can be used once if you lose access to your authenticator device.</p>
                                <pre class="two-factor-recovery" data-two-factor-recovery>Loading recovery codes...</pre>

                                <form method="POST" action="{{ route('two-factor.regenerate-recovery-codes') }}" class="auth-form">
                                    @csrf

                                    <div class="auth-actions">
                                        <button type="submit" class="button-link-muted">Regenerate recovery codes</button>
                                    </div>
                                </form>
                            @endif
                        </div>
                    </div>

                    <form method="POST" action="{{ route('two-factor.disable') }}" class="auth-form auth-form-inline">
                        @csrf
                        @method('DELETE')

                        <div class="auth-actions">
                            <button type="submit" class="button-link-muted">Disable two-factor authentication</button>
                        </div>
                    </form>
                @endif
            </article>
        @endif
    </section>
@endsection
