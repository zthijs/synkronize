import { Injectable, Logger } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import SpotifyWebApi from 'spotify-web-api-node';
import { Repository } from 'typeorm';
import { Provider } from '../provider.entity';
import { ProviderEnum } from '@/common/enums/providers.enum';

@Injectable()
export class SpotifyService {
  private readonly logger = new Logger(SpotifyService.name);

  constructor(
    @InjectRepository(Provider)
    private providerRepository: Repository<Provider>,
  ) {}

  async getSpotifyAccount(id: string): Promise<Provider> {
    return this.providerRepository.findOne({
      where: { id, provider: ProviderEnum.Spotify },
    });
  }

  async getAuthorizationURL(): Promise<string> {
    const spotifyClient = new SpotifyWebApi({
      clientId: process.env.SPOTIFY_CLIENT_ID,
      clientSecret: process.env.SPOTIFY_CLIENT_SECRET,
      redirectUri: process.env.SPOTIFY_REDIRECT_URI,
    });

    return spotifyClient.createAuthorizeURL(
      ['user-read-playback-state', 'user-read-currently-playing'],
      '',
    );
  }

  async upsertSpotifyAccount(code: string): Promise<Provider> {
    const spotifyClient = new SpotifyWebApi({
      clientId: process.env.SPOTIFY_CLIENT_ID,
      clientSecret: process.env.SPOTIFY_CLIENT_SECRET,
      redirectUri: process.env.SPOTIFY_REDIRECT_URI,
    });

    try {
      const {
        body: { access_token, refresh_token },
      } = await spotifyClient.authorizationCodeGrant(code);

      spotifyClient.setAccessToken(access_token);
      spotifyClient.setRefreshToken(refresh_token);

      const {
        body: { id, display_name },
      } = await spotifyClient.getMe();

      const existingAccount = await this.providerRepository.findOne({
        where: { id },
      });

      if (existingAccount) {
        existingAccount.accessToken = access_token;
        existingAccount.refreshToken = refresh_token;
        existingAccount.provider = ProviderEnum.Spotify;
        existingAccount.displayName = display_name;
        return this.providerRepository.save(existingAccount);
      }

      const newAccount = this.providerRepository.create({
        id,
        accessToken: access_token,
        refreshToken: refresh_token,
        provider: ProviderEnum.Spotify,
        displayName: display_name,
      });

      return this.providerRepository.save(newAccount);
    } catch (error) {
      this.logger.error('Error during Spotify account upsert:', error);
      throw new Error('Failed to upsert Spotify account');
    }
  }

  async toggleSpotifyAccount(id: string, enabled: boolean): Promise<Provider> {
    const spotifyAccount = await this.providerRepository.findOne({
      where: { id },
    });

    if (spotifyAccount) {
      spotifyAccount.enabled = enabled;
      return this.providerRepository.save(spotifyAccount);
    }

    this.logger.error(`Spotify account ${id} not found`);
    throw new Error(`Spotify account ${id} not found`);
  }

  async getActiveSpotifyAccounts() {
    const accountsToSync = await this.providerRepository.find({
      where: { enabled: true },
      relations: ['consumers'],
    });

    const accounts = accountsToSync.map(async (account) => {
      const currentPlayback = await this.getCurrentPlayback(account);
      if (currentPlayback) {
        return {
          status: currentPlayback,
          account,
        };
      }
      return false;
    });

    return (await Promise.all(accounts)).filter((account) => account !== false);
  }

  private async getCurrentPlayback(account: Provider) {
    const spotifyClient = new SpotifyWebApi({
      clientId: process.env.SPOTIFY_CLIENT_ID,
      clientSecret: process.env.SPOTIFY_CLIENT_SECRET,
      redirectUri: process.env.SPOTIFY_REDIRECT_URI,
    });

    await this.ensureValidToken(spotifyClient, account);

    const { body } = await spotifyClient.getMyCurrentPlaybackState();

    if (body.is_playing && body.item) {
      switch (body.item.type) {
        case 'episode': {
          const { name, show } = body.item;
          return {
            id: body.item.id,
            name,
            artists: show.publisher,
            album: show.name,
            image: show.images[0].url,
          };
        }

        case 'track': {
          const { name, artists, album } = body.item;
          return {
            id: body.item.id,
            name,
            artists: artists.map((artist: any) => artist.name).join(', '),
            album: album.name,
            image: album.images[0].url,
          };
        }

        default: {
          return false;
        }
      }
    } else {
      return false;
    }
  }

  private async ensureValidToken(
    spotifyClient: SpotifyWebApi,
    account: Provider,
  ) {
    spotifyClient.setAccessToken(account.accessToken);
    spotifyClient.setRefreshToken(account.refreshToken);

    try {
      await spotifyClient.getMe();
    } catch (error) {
      if (error.statusCode === 401) {
        const data = await spotifyClient.refreshAccessToken();
        const { access_token } = data.body;

        account.accessToken = access_token;
        await this.providerRepository.save(account);

        spotifyClient.setAccessToken(access_token);
      } else {
        this.logger.error('Error ensuring valid token:', error);
        throw error;
      }
    }
  }
}
