<?php

namespace App\Http\Controllers;

use Illuminate\Contracts\View\View;
use Laravel\Fortify\Features;

class AccountController extends Controller
{
    public function __invoke(): View
    {
        return view('account', [
            'canVerifyEmail' => Features::enabled(Features::emailVerification()),
            'canUpdateProfile' => Features::enabled(Features::updateProfileInformation()),
            'canUpdatePassword' => Features::enabled(Features::updatePasswords()),
            'canManageTwoFactor' => Features::enabled(Features::twoFactorAuthentication()),
        ]);
    }
}
