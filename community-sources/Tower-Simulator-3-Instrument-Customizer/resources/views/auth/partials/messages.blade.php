@if (session('status'))
    <div class="auth-message auth-message-success">
        {{ session('status') }}
    </div>
@endif

@if ($errors->any())
    <div class="auth-message auth-message-error">
        <strong>There is a problem with the submitted form.</strong>
        <ul class="auth-error-list">
            @foreach ($errors->all() as $error)
                <li>{{ $error }}</li>
            @endforeach
        </ul>
    </div>
@endif
