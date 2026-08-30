<!DOCTYPE html>
<html lang="{{ str_replace('_', '-', app()->getLocale()) }}">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{{ $title ?? 'TS3IC' }}</title>
        @vite(['resources/css/app.css', 'resources/js/app.js'])
    </head>
    <body>
        <div class="shell">
            <header class="topbar">
                <div>
                    <a class="brand" href="{{ route('dashboard') }}">TS3IC</a>
                    <p class="tagline">Tower Simulator 3 instrument customizer rebuild.</p>
                </div>

                <nav class="nav-links">
                    <a href="{{ route('dashboard') }}" @class(['is-active' => request()->routeIs('dashboard')])>Home</a>
                    @auth
                        <a href="{{ route('workspaces.index') }}" @class(['is-active' => request()->routeIs('workspaces.*')])>Workspaces</a>
                        <a href="{{ route('account') }}" @class(['is-active' => request()->routeIs('account')])>Account</a>
                        <form method="POST" action="{{ route('logout') }}">
                            @csrf
                            <button type="submit" class="nav-button">Log out</button>
                        </form>
                    @else
                        <a href="{{ route('login') }}" @class(['is-active' => request()->routeIs('login')])>Log in</a>
                        <a href="{{ route('register') }}" @class(['is-active' => request()->routeIs('register')])>Register</a>
                    @endauth
                </nav>
            </header>

            <main class="page">
                @yield('content')
            </main>
        </div>
    </body>
</html>
